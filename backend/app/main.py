"""FastAPI entry point for the RailSync simulated decision-support demo."""

from __future__ import annotations

import asyncio
import copy
import os
import threading
from contextlib import suppress
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from app.auth import authenticate, issue_token, verify_token
from app.conflict_detection import detect_section_conflicts
from app.database import get_logs, log_decision
from app.llm_narration import narrate_decision
from app.model_loader import (
    get_feature_importance,
    get_model_metrics,
    get_model_scope,
    is_model_loaded,
)
from app.models import TrainStatus
from app.network import network_payload
from app.resolver import resolve_conflicts
from app.simulator import Simulator


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

TICK_SECONDS = max(0.2, float(os.getenv("SIMULATION_TICK_SECONDS", "2")))


def require_auth(authorization: str = Header(default="")) -> dict:
    """Resolve a Bearer token into an authenticated token payload."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing or malformed authorization header")
    payload = verify_token(authorization[len("Bearer "):].strip())
    if payload is None:
        raise HTTPException(status_code=401, detail="invalid or expired token")
    return payload


def require_role(role: str):
    def _check(payload: dict = Depends(require_auth)) -> dict:
        if payload.get("role") != role:
            raise HTTPException(status_code=403, detail=f"this action requires the '{role}' role")
        return payload

    return _check


simulator = Simulator()
approved_decisions: set[str] = set()
rejected_decisions: set[str] = set()
logged_decisions: set[str] = set()
narrated_decisions: dict[str, str] = {}

_state_lock = threading.RLock()
_live_state: dict | None = None
_simulation_task: asyncio.Task | None = None


def _compute_full_state() -> dict:
    """Create one state payload and record only genuine simulated events."""
    sim_state = simulator.get_state()
    conflicts = detect_section_conflicts(sim_state)
    simulator.observe_conflicts(conflicts)
    resolutions = resolve_conflicts(conflicts, sim_state)

    for resolution in resolutions:
        decision_id = resolution["decision_id"]
        resolution["approval_status"] = (
            "approved"
            if decision_id in approved_decisions
            else "rejected"
            if decision_id in rejected_decisions
            else "pending"
        )
        if decision_id in narrated_decisions:
            resolution["reason"] = narrated_decisions[decision_id]
        elif decision_id not in logged_decisions:
            resolution["reason"] = narrate_decision(resolution["reason"])
            narrated_decisions[decision_id] = resolution["reason"]
            logged_decisions.add(decision_id)
            log_decision(
                sim_timestamp=sim_state["sim_time"],
                conflict_type="section",
                trains_involved=[resolution["winner_train"]] + resolution["held_trains"],
                action_taken="rule_based_recommendation",
                reason=resolution["reason"],
                resolved_by="simulation",
            )

    for event in simulator.platform_mgr.pop_events():
        log_decision(
            sim_timestamp=sim_state["sim_time"],
            conflict_type=event["type"],
            trains_involved=[event["train_no"]],
            action_taken=event["type"],
            reason=event["detail"],
            resolved_by="simulation",
        )

    return {**sim_state, "conflicts": conflicts, "resolutions": resolutions}


def _refresh_live_state() -> dict:
    global _live_state
    _live_state = _compute_full_state()
    return _live_state


def _current_live_state() -> dict:
    with _state_lock:
        if _live_state is None:
            _refresh_live_state()
        return copy.deepcopy(_live_state)


async def _simulation_loop() -> None:
    """Advance one shared simulation regardless of connected WebSocket clients."""
    while True:
        with _state_lock:
            simulator.tick()
            _refresh_live_state()
        await asyncio.sleep(TICK_SECONDS)


@app.on_event("startup")
async def start_simulation_loop() -> None:
    global _simulation_task
    with _state_lock:
        _refresh_live_state()
    if _simulation_task is None or _simulation_task.done():
        _simulation_task = asyncio.create_task(_simulation_loop())


@app.on_event("shutdown")
async def stop_simulation_loop() -> None:
    global _simulation_task
    if _simulation_task:
        _simulation_task.cancel()
        with suppress(asyncio.CancelledError):
            await _simulation_task
        _simulation_task = None


@app.get("/")
def health():
    return {
        "status": "ok",
        "service": "RailSync backend",
        "model_loaded": is_model_loaded(),
        "scope": get_model_scope(),
    }


class LoginRequest(BaseModel):
    username: str
    password: str


@app.post("/api/auth/login")
def login(request: LoginRequest):
    user = authenticate(request.username.strip(), request.password)
    if user is None:
        raise HTTPException(status_code=401, detail="invalid credentials")
    token = issue_token(user["username"], user["role"])
    return {"token": token, "user": user}


@app.get("/api/auth/me")
def auth_me(payload: dict = Depends(require_auth)):
    return payload


@app.get("/api/network")
def get_network():
    return network_payload()


@app.get("/api/state")
def get_state():
    return _current_live_state()


@app.get("/api/analytics")
def get_analytics(payload: dict = Depends(require_role("controller"))):
    with _state_lock:
        return simulator.get_analytics()


@app.get("/api/model-info")
def model_info():
    return {
        "model_loaded": is_model_loaded(),
        "model_name": "XGBoost synthetic delay regressor",
        "scope": get_model_scope(),
        "metrics": get_model_metrics(),
        "feature_importance": get_feature_importance(),
    }


@app.get("/api/logs")
def api_get_logs(train_no: str | None = None, payload: dict = Depends(require_role("controller"))):
    return get_logs(train_no=train_no)


class WhatIfRequest(BaseModel):
    train_no: str
    extra_delay_minutes: float = Field(ge=0, le=240)


@app.post("/api/whatif")
def whatif(request: WhatIfRequest, payload: dict = Depends(require_role("controller"))):
    with _state_lock:
        snapshot = copy.deepcopy(simulator.get_state())
        target = next((train for train in snapshot["trains"] if train["train_no"] == request.train_no), None)
        if not target:
            raise HTTPException(status_code=404, detail="train not found")
        target["predicted_delay_min"] += request.extra_delay_minutes

        conflicts = detect_section_conflicts(snapshot)
        resolutions = resolve_conflicts(conflicts, snapshot)
        total_projected_delay = sum(train["predicted_delay_min"] for train in snapshot["trains"])
        # Narrate each projected resolution's reason via the LLM (OpenRouter/MiniMax or Ollama fallback)
        for resolution in resolutions:
            decision_id = resolution["decision_id"]
            if decision_id in narrated_decisions:
                resolution["reason"] = narrated_decisions[decision_id]
            else:
                resolution["reason"] = narrate_decision(resolution["reason"])
                narrated_decisions[decision_id] = resolution["reason"]
        log_decision(
            sim_timestamp=simulator.sim_time.strftime("%Y-%m-%d %H:%M"),
            conflict_type="what_if",
            trains_involved=[request.train_no],
            action_taken="simulated_delay",
            reason=(
                f"Controller simulated {request.extra_delay_minutes} additional delay minutes "
                f"for {request.train_no}."
            ),
            resolved_by="controller",
        )
    return {
        "injected_train": request.train_no,
        "injected_extra_minutes": request.extra_delay_minutes,
        "projected_conflicts": conflicts,
        "projected_resolutions": resolutions,
        "total_projected_network_delay": round(total_projected_delay, 1),
    }


class OverrideRequest(BaseModel):
    train_no: str
    action: str
    admin_note: str = ""


class ApprovalRequest(BaseModel):
    decision_id: str
    approved: bool = True
    controller_note: str = ""


@app.post("/api/decisions/approve")
def approve_decision(request: ApprovalRequest, payload: dict = Depends(require_role("controller"))):
    with _state_lock:
        sim_state = simulator.get_state()
        current_resolutions = resolve_conflicts(detect_section_conflicts(sim_state), sim_state)
        matching = next((item for item in current_resolutions if item["decision_id"] == request.decision_id), None)
        if matching is None:
            raise HTTPException(status_code=409, detail="recommendation is no longer active")

        if request.approved:
            approved_decisions.add(request.decision_id)
            rejected_decisions.discard(request.decision_id)
            changed_trains = simulator.apply_controller_decision(
                request.decision_id,
                matching["winner_train"],
                matching["held_trains"],
                matching["section"],
            )
            if changed_trains:
                simulator.record_controller_resolution()
            action = "controller_approved_rule_based_recommendation"
            reason = request.controller_note or "Controller approved the simulated rule-based recommendation."
        else:
            approved_decisions.discard(request.decision_id)
            rejected_decisions.add(request.decision_id)
            changed_trains = simulator.clear_controller_decision(request.decision_id)
            action = "controller_rejected_or_released_recommendation"
            reason = request.controller_note or "Controller rejected or released the simulated rule-based recommendation."

        log_decision(
            sim_timestamp=simulator.sim_time.strftime("%Y-%m-%d %H:%M"),
            conflict_type="section",
            trains_involved=[matching["winner_train"]] + matching["held_trains"],
            action_taken=action,
            reason=reason,
            resolved_by="controller",
        )
        _refresh_live_state()

    return {
        "success": True,
        "decision_id": request.decision_id,
        "approved": request.approved,
        "controller_hold_applied": bool(request.approved and changed_trains),
        "held_trains": changed_trains if request.approved else [],
        "released_trains": changed_trains if not request.approved else [],
    }


@app.post("/api/override")
def override(request: OverrideRequest, payload: dict = Depends(require_role("controller"))):
    supported_actions = {"force_proceed", "hold_train", "release_manual_hold"}
    if request.action not in supported_actions:
        raise HTTPException(status_code=400, detail=f"unsupported action; choose one of {sorted(supported_actions)}")

    with _state_lock:
        train = simulator.trains_by_no.get(request.train_no)
        if not train:
            raise HTTPException(status_code=404, detail="train not found")

        success = False
        error = None
        if request.action == "force_proceed":
            if train.status != TrainStatus.WAITING:
                error = "force_proceed is available only for a train waiting for a platform"
            else:
                station = train.current_to
                platform = simulator.platform_mgr.assign_platform(station, train.train_no)
                if platform is None:
                    error = f"no platform is currently free at {station}"
                else:
                    simulator._seat_at_platform(
                        train,
                        station,
                        platform,
                        "Controller override: allocated available platform",
                    )
                    success = True
        elif request.action == "hold_train":
            success = simulator.apply_manual_hold(request.train_no)
            if not success:
                error = "manual holds are available only for an active moving/checking train"
        else:
            success = simulator.release_manual_hold(request.train_no)
            if not success:
                error = "this train has no active manual hold"

        if not success:
            return {"success": False, "error": error, "train_no": request.train_no, "action": request.action}

        log_decision(
            sim_timestamp=simulator.sim_time.strftime("%Y-%m-%d %H:%M"),
            conflict_type="admin_override",
            trains_involved=[request.train_no],
            action_taken=request.action,
            reason=request.admin_note or f"Controller override: {request.action}",
            resolved_by="controller",
        )
        _refresh_live_state()
        new_conflicts = detect_section_conflicts(simulator.get_state())

    return {
        "success": True,
        "train_no": request.train_no,
        "action": request.action,
        "new_conflicts_after_override": new_conflicts,
    }


class SpeedRequest(BaseModel):
    multiplier: float = Field(ge=0.25, le=10)


@app.post("/api/simulation/pause")
def pause_sim(payload: dict = Depends(require_role("controller"))):
    with _state_lock:
        simulator.pause()
        log_decision(
            sim_timestamp=simulator.sim_time.strftime("%Y-%m-%d %H:%M"),
            conflict_type="simulation_control",
            trains_involved=[],
            action_taken="pause",
            reason="Controller paused the simulation.",
            resolved_by="controller",
        )
        _refresh_live_state()
    return {"paused": True}


@app.post("/api/simulation/resume")
def resume_sim(payload: dict = Depends(require_role("controller"))):
    with _state_lock:
        simulator.resume()
        log_decision(
            sim_timestamp=simulator.sim_time.strftime("%Y-%m-%d %H:%M"),
            conflict_type="simulation_control",
            trains_involved=[],
            action_taken="resume",
            reason="Controller resumed the simulation.",
            resolved_by="controller",
        )
        _refresh_live_state()
    return {"paused": False}


@app.post("/api/simulation/reset")
def reset_sim(payload: dict = Depends(require_role("controller"))):
    with _state_lock:
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
        _refresh_live_state()
    return {"reset": True, "sim_time": simulator.sim_time.strftime("%Y-%m-%d %H:%M")}


@app.post("/api/simulation/speed")
def set_speed(request: SpeedRequest, payload: dict = Depends(require_role("controller"))):
    with _state_lock:
        simulator.set_speed(request.multiplier)
        log_decision(
            sim_timestamp=simulator.sim_time.strftime("%Y-%m-%d %H:%M"),
            conflict_type="simulation_control",
            trains_involved=[],
            action_taken="set_speed",
            reason=f"Controller set simulation speed to {simulator.speed_multiplier}x.",
            resolved_by="controller",
        )
        _refresh_live_state()
    return {"speed_multiplier": simulator.speed_multiplier}


@app.websocket("/ws/live")
async def websocket_live(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            await websocket.send_json(_current_live_state())
            await asyncio.sleep(TICK_SECONDS)
    except WebSocketDisconnect:
        pass
