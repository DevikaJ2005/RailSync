"""
RailSync Backend — FastAPI app.

Run: uvicorn app.main:app --reload --port 8000
"""

import asyncio
import copy
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from app.network import network_payload
from app.simulator import Simulator
from app.models import TrainStatus
from app.conflict_detection import detect_section_conflicts
from app.resolver import resolve_conflicts
from app.llm_narration import narrate_decision
from app.database import log_decision, get_logs
from app.model_loader import is_model_loaded, get_feature_importance, get_model_metrics

app = FastAPI(title="RailSync API")

origins = os.getenv(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:5174,http://127.0.0.1:5173,http://127.0.0.1:5174",
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TICK_SECONDS = float(os.getenv("SIMULATION_TICK_SECONDS", "2"))

simulator = Simulator()
approved_decisions = set()
rejected_decisions = set()
logged_decisions = set()
narrated_decisions = {}


@app.get("/")
def health():
    return {"status": "ok", "service": "RailSync backend", "model_loaded": is_model_loaded()}


@app.get("/api/network")
def get_network():
    return network_payload()


@app.get("/api/state")
def get_state():
    return _compute_full_state()


@app.get("/api/analytics")
def get_analytics():
    return simulator.get_analytics()


@app.get("/api/model-info")
def model_info():
    return {
        "model_loaded": is_model_loaded(),
        "model_name": "XGBoost delay regressor",
        "metrics": get_model_metrics(),
        "feature_importance": get_feature_importance(),
    }


@app.get("/api/logs")
def api_get_logs(train_no: str = None):
    return get_logs(train_no=train_no)


class WhatIfRequest(BaseModel):
    train_no: str
    extra_delay_minutes: float


@app.post("/api/whatif")
def whatif(req: WhatIfRequest):
    snapshot = copy.deepcopy(simulator.get_state())
    for t in snapshot["trains"]:
        if t["train_no"] == req.train_no:
            t["predicted_delay_min"] += req.extra_delay_minutes

    conflicts = detect_section_conflicts(snapshot)
    resolutions = resolve_conflicts(conflicts, snapshot)
    total_projected_delay = sum(t["predicted_delay_min"] for t in snapshot["trains"])

    result = {
        "injected_train": req.train_no,
        "injected_extra_minutes": req.extra_delay_minutes,
        "projected_conflicts": conflicts,
        "projected_resolutions": resolutions,
        "total_projected_network_delay": round(total_projected_delay, 1),
    }
    log_decision(
        sim_timestamp=simulator.sim_time.strftime("%Y-%m-%d %H:%M"),
        conflict_type="what_if",
        trains_involved=[req.train_no],
        action_taken="simulated_delay",
        reason=f"Controller simulated {req.extra_delay_minutes} extra delay minutes for {req.train_no}.",
        resolved_by="controller",
    )
    return result


class OverrideRequest(BaseModel):
    train_no: str
    action: str
    admin_note: str = ""


class ApprovalRequest(BaseModel):
    decision_id: str
    approved: bool = True
    controller_note: str = ""


@app.post("/api/decisions/approve")
def approve_decision(req: ApprovalRequest):
    sim_state = simulator.get_state()
    current_resolutions = resolve_conflicts(detect_section_conflicts(sim_state), sim_state)
    matching_resolution = next((r for r in current_resolutions if r["decision_id"] == req.decision_id), None)

    if req.approved:
        approved_decisions.add(req.decision_id)
        rejected_decisions.discard(req.decision_id)
        action = "controller_approved"
        reason = req.controller_note or "Controller approved the ML recommendation."
        changed_trains = []
        if matching_resolution:
            changed_trains = simulator.apply_controller_decision(
                req.decision_id,
                matching_resolution["winner_train"],
                matching_resolution["held_trains"],
                matching_resolution["section"],
            )
    else:
        approved_decisions.discard(req.decision_id)
        rejected_decisions.add(req.decision_id)
        action = "controller_rejected"
        reason = req.controller_note or "Controller rejected the ML recommendation."
        changed_trains = simulator.clear_controller_decision(req.decision_id)

    decision_parts = req.decision_id.split("|")
    trains_involved = decision_parts[1:2] + (decision_parts[2].split(",") if len(decision_parts) > 2 else [])

    log_decision(
        sim_timestamp=simulator.sim_time.strftime("%Y-%m-%d %H:%M"),
        conflict_type="section",
        trains_involved=trains_involved,
        action_taken=action,
        reason=reason,
        resolved_by="controller",
    )
    return {
        "success": True,
        "decision_id": req.decision_id,
        "approved": req.approved,
        "movement_authority_applied": bool(req.approved and changed_trains),
        "held_trains": changed_trains if req.approved else [],
        "released_trains": changed_trains if not req.approved else [],
    }


@app.post("/api/override")
def override(req: OverrideRequest):
    train = simulator.trains_by_no.get(req.train_no)
    if not train:
        return {"success": False, "error": "train not found"}

    if req.action == "force_proceed" and train.status == TrainStatus.WAITING:
        station = train.current_to
        platform = simulator.platform_mgr.assign_platform(station, train.train_no)
        if platform:
            simulator._seat_at_platform(train, station, platform, "Admin override — forced onto platform")

    log_decision(
        sim_timestamp=simulator.sim_time.strftime("%Y-%m-%d %H:%M"),
        conflict_type="admin_override",
        trains_involved=[req.train_no],
        action_taken=req.action,
        reason=req.admin_note or f"Admin override: {req.action}",
        resolved_by="admin",
    )

    # re-check for any new conflicts this override might have created
    state = simulator.get_state()
    new_conflicts = detect_section_conflicts(state)

    return {"success": True, "new_conflicts_after_override": new_conflicts}


class SpeedRequest(BaseModel):
    multiplier: float


@app.post("/api/simulation/pause")
def pause_sim():
    simulator.pause()
    log_decision(
        sim_timestamp=simulator.sim_time.strftime("%Y-%m-%d %H:%M"),
        conflict_type="simulation_control",
        trains_involved=[],
        action_taken="pause",
        reason="Controller paused the simulation.",
        resolved_by="controller",
    )
    return {"paused": True}


@app.post("/api/simulation/resume")
def resume_sim():
    simulator.resume()
    log_decision(
        sim_timestamp=simulator.sim_time.strftime("%Y-%m-%d %H:%M"),
        conflict_type="simulation_control",
        trains_involved=[],
        action_taken="resume",
        reason="Controller resumed the simulation.",
        resolved_by="controller",
    )
    return {"paused": False}


@app.post("/api/simulation/reset")
def reset_sim():
    simulator.reset()
    approved_decisions.clear()
    rejected_decisions.clear()
    logged_decisions.clear()
    narrated_decisions.clear()
    log_decision(
        sim_timestamp=simulator.sim_time.strftime("%Y-%m-%d %H:%M"),
        conflict_type="simulation_control",
        trains_involved=[],
        action_taken="reset",
        reason="Controller reset the simulation state.",
        resolved_by="controller",
    )
    return {"reset": True, "sim_time": simulator.sim_time.strftime("%Y-%m-%d %H:%M")}


@app.post("/api/simulation/speed")
def set_speed(req: SpeedRequest):
    simulator.set_speed(req.multiplier)
    log_decision(
        sim_timestamp=simulator.sim_time.strftime("%Y-%m-%d %H:%M"),
        conflict_type="simulation_control",
        trains_involved=[],
        action_taken="set_speed",
        reason=f"Controller set simulation speed to {simulator.speed_multiplier}x.",
        resolved_by="controller",
    )
    return {"speed_multiplier": simulator.speed_multiplier}


def _compute_full_state():
    sim_state = simulator.get_state()
    conflicts = detect_section_conflicts(sim_state)
    resolutions = resolve_conflicts(conflicts, sim_state)

    for r in resolutions:
        r["approval_status"] = (
            "approved" if r["decision_id"] in approved_decisions
            else "rejected" if r["decision_id"] in rejected_decisions
            else "pending"
        )
        if r["decision_id"] in narrated_decisions:
            r["reason"] = narrated_decisions[r["decision_id"]]
        if r["decision_id"] not in logged_decisions:
            r["reason"] = narrate_decision(r["reason"])
            narrated_decisions[r["decision_id"]] = r["reason"]
            logged_decisions.add(r["decision_id"])
            log_decision(
                sim_timestamp=sim_state["sim_time"],
                conflict_type="section",
                trains_involved=[r["winner_train"]] + r["held_trains"],
                action_taken="ml_recommendation",
                reason=r["reason"],
                resolved_by="ml",
            )

    for ev in simulator.platform_mgr.pop_events():
        log_decision(
            sim_timestamp=sim_state["sim_time"],
            conflict_type=ev["type"],
            trains_involved=[ev["train_no"]],
            action_taken=ev["type"],
            reason=ev["detail"],
            resolved_by="ai",
        )

    simulator.conflicts_detected += len(conflicts)
    simulator.conflicts_resolved += len(resolutions)

    total_delay_now = sum(t["predicted_delay_min"] for t in sim_state["trains"])
    saved = sum(5 for _ in resolutions)  # simple attribution: each resolution avoids ~5 min pileup
    simulator.total_delay_accum_without_ai += total_delay_now + saved
    simulator.total_delay_accum_with_ai += total_delay_now

    return {**sim_state, "conflicts": conflicts, "resolutions": resolutions}


@app.websocket("/ws/live")
async def websocket_live(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            simulator.tick()
            state = _compute_full_state()
            await websocket.send_json(state)
            await asyncio.sleep(TICK_SECONDS)
    except WebSocketDisconnect:
        pass
