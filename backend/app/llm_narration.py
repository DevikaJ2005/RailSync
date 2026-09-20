"""MiniMax LLM Explanation and Narration Layer for RailSync.

This module provides clear, concise, natural-language controller explanations
derived strictly from authoritative deterministic decision evidence.

The deterministic backend decides. MiniMax explains.
The LLM never makes or modifies decisions.
"""

from __future__ import annotations

import json
import os
import re
import time
import requests

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MINIMAX_DIRECT_URL = os.getenv("MINIMAX_API_URL", "https://api.minimax.chat/v1/text/chatcompletion_v2")
OLLAMA_URL = "http://localhost:11434/api/generate"

OPENROUTER_TIMEOUT_SECONDS = int(os.getenv("OPENROUTER_TIMEOUT_SECONDS", "15"))
MINIMAX_TIMEOUT_SECONDS = int(os.getenv("MINIMAX_TIMEOUT_SECONDS", "15"))
OLLAMA_TIMEOUT_SECONDS = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "20"))
RETRY_COOLDOWN_SECONDS = 60

SYSTEM_PROMPT = (
    "You are RailSync's controller explanation assistant.\n\n"
    "The operational decision has already been made by a deterministic railway traffic decision engine.\n\n"
    "Your ONLY job is to explain the supplied decision evidence in clear, concise, natural language for a railway controller.\n\n"
    "The deterministic decision engine remains authoritative. You do NOT make or modify operational decisions.\n\n"
    "The explanation must answer:\n"
    "- WHY is this train being allowed to continue?\n"
    "- WHY is the other train being asked to wait?\n\n"
    "Good examples:\n"
    '- "T108 is recommended to continue first because it has higher priority under the current operating policy and lower accumulated delay. T101 will wait at the section approach until the block is clear."\n'
    '- "T101 is allowed to proceed because it has been held longer and is approaching its scheduled station stop. Holding T108 here minimises total system delay."\n\n'
    "STRICT NEGATIVE CONSTRAINTS:\n"
    "MiniMax must NEVER output internal terminology:\n"
    '- "deterministic train-number tie-breaker"\n'
    '- "operational_class"\n'
    '- "starvation safeguard"\n'
    '- "priority score"\n'
    '- "decision_id"\n'
    '- "event_id"\n'
    '- "projected occupancy window"\n'
    '- "model feature"\n'
    '- "XGBoost prediction"\n'
    '- "XGBoost"\n'
    "MiniMax must NEVER output raw feature values or internal mathematical scores (e.g. '0.83 beats 0.41' or 'score of 30').\n"
    "MiniMax must NEVER hallucinate:\n"
    "- track conditions not in evidence\n"
    "- signal aspects not in simulation (e.g. green, yellow, or red signals)\n"
    "- speed limits not modeled\n"
    "- passenger counts not modeled\n"
    "- weather or equipment failures unless explicitly provided in simulation evidence\n"
    "MiniMax must NEVER claim a conflict is a collision or use catastrophic language (e.g. 'collision avoided', 'crash prevented').\n"
    "MiniMax must NEVER claim RailSync guarantees railway safety.\n\n"
    "If evidence is insufficient to explain the recommendation, output exactly:\n"
    '"RailSync cannot provide a more specific explanation from the available simulation data."\n\n'
    "Keep explanations concise (2–3 sentences max).\n"
    "Return only explanation text, with no headings, markdown formatting, greetings, quotes, or disclaimers."
)

LOG_SYSTEM_PROMPT = (
    "You are RailSync's controller log explanation assistant.\n\n"
    "Explain recorded operational log events in clear, professional controller language.\n"
    "Event types include: HOLD APPROVED, HOLD REJECTED, RECOMMENDATION APPROVED, RECOMMENDATION REJECTED, TRAIN WAITING, TRAIN RESUMED, PLATFORM UNAVAILABLE.\n\n"
    "The explanation must answer what occurred and why in operational terms.\n"
    "Keep log explanations concise (2–3 sentences max).\n"
    "Never invent facts, physical track conditions, signalling aspects, or collision risks.\n"
    "Never mention internal technical terms (e.g. XGBoost, priority score, decision_id, starvation safeguard).\n"
    "If evidence is insufficient, output exactly:\n"
    '"RailSync cannot provide a more specific explanation from the available simulation data."\n\n'
    "Return only explanation text, with no headings, markdown formatting, greetings, quotes, or disclaimers."
)

_unavailable_until = {"openrouter": 0.0, "minimax": 0.0, "ollama": 0.0}


def _normalize_evidence(context: dict) -> dict:
    """Extract standard trusted evidence fields regardless of nesting."""
    event = context.get("event") or context
    evidence = event.get("decision_evidence") or context.get("decision_evidence") or {}

    selected_train = (
        event.get("selected_train")
        or evidence.get("selected_train")
        or context.get("recommendation", {}).get("proceed_train")
        or context.get("proceed_train")
    )
    hold_trains = (
        event.get("hold_trains")
        or evidence.get("trains_requiring_hold")
        or context.get("recommendation", {}).get("held_trains")
        or context.get("held_trains")
        or []
    )
    unaffected_trains = (
        event.get("unaffected_trains")
        or evidence.get("unaffected_trains")
        or context.get("recommendation", {}).get("unaffected_trains")
        or []
    )
    section = (
        event.get("section")
        or evidence.get("section")
        or context.get("conflict", {}).get("section")
        or ""
    ).replace(" <-> ", " → ")

    raw_status = (
        event.get("conflict_status")
        or event.get("conflict_type")
        or evidence.get("conflict_type")
        or context.get("conflict", {}).get("status")
        or "active"
    )
    conflict_type = "projected" if raw_status in ("predicted", "forecast", "projected") else "active"

    reason_type = (
        event.get("reason_type")
        or evidence.get("reason_type")
        or ("starvation_safeguard" if evidence.get("selection_rule") == "starvation_safeguard" else None)
        or "operational_class"
    )

    reason = (
        event.get("reason_text")
        or event.get("reason")
        or evidence.get("operational_summary")
        or context.get("reason")
        or ""
    )

    controller_action = (
        event.get("controller_action")
        or context.get("controller_action")
        or ("approved" if "approved" in str(event.get("action", "")).lower() else "rejected" if "rejected" in str(event.get("action", "")).lower() else None)
    )

    action_name = str(event.get("action") or event.get("action_taken") or "").lower()
    event_type = (
        event.get("event_type")
        or ("CONTROLLER_ACTION" if controller_action else
            "PLATFORM_UNAVAILABLE" if action_name == "held" or reason_type == "platform_unavailable" else
            "TRAIN_RESUMED" if action_name in ("resume", "release_manual_hold", "resumed") or reason_type == "manual_resume" else
            "TRAIN_WAITING" if action_name in ("hold_train", "waiting") or reason_type == "manual_hold" else
            "RECOMMENDATION")
    )

    station = event.get("station") or context.get("station")
    if not station and " at " in reason:
        # e.g. "no free platform at Salem Junction"
        station = reason.split(" at ")[-1].rstrip(".")

    raw_trains = (
        event.get("trains_involved")
        or evidence.get("trains_involved_profiles")
        or context.get("trains_involved")
        or []
    )
    allowed_train_ids = set()
    for t in raw_trains:
        if isinstance(t, dict):
            allowed_train_ids.add(t.get("train_id") or t.get("train_no"))
        elif isinstance(t, str):
            allowed_train_ids.add(t)
    if selected_train:
        allowed_train_ids.add(selected_train)
    for h in hold_trains:
        allowed_train_ids.add(h)
    for u in unaffected_trains:
        allowed_train_ids.add(u)

    winner_type = "Express"
    if isinstance(evidence.get("winner"), dict):
        winner_type = evidence["winner"].get("train_type") or "Express"

    overlap = (
        event.get("expected_overlap_minutes")
        or context.get("expected_overlap_minutes")
        or event.get("overlap_minutes")
        or context.get("overlap_minutes")
        or context.get("conflict", {}).get("overlap_minutes")
        or evidence.get("expected_overlap_minutes")
        or evidence.get("conflict", {}).get("expected_overlap_minutes")
    )

    return {
        "event_type": event_type,
        "conflict_type": conflict_type,
        "section": section,
        "selected_train": selected_train,
        "hold_trains": list(hold_trains),
        "unaffected_trains": list(unaffected_trains),
        "allowed_train_ids": allowed_train_ids,
        "reason_type": reason_type,
        "reason": reason,
        "controller_action": controller_action,
        "station": station,
        "winner_type": winner_type,
        "overlap_minutes": overlap,
    }


def build_deterministic_fallback(context: dict) -> str:
    """Construct an authoritative explanation from evidence without generic boilerplate."""
    ev = _normalize_evidence(context)
    selected = ev["selected_train"]
    holds = ev["hold_trains"]
    section = ev["section"]
    reason_type = ev["reason_type"]
    conflict_type = ev["conflict_type"]
    action = ev["controller_action"]
    station = ev["station"]

    # Insufficient evidence fallback
    if not selected and not holds and not station and not ev["allowed_train_ids"] and not ev["reason"]:
        return "RailSync cannot provide a more specific explanation from the available simulation data."

    # Train resumed event
    if ev["event_type"] in ("TRAIN_RESUMED", "RESUME") or reason_type == "manual_resume":
        target = holds[0] if holds else (selected if selected else (next(iter(ev["allowed_train_ids"])) if ev["allowed_train_ids"] else "The train"))
        loc = f" at {station}" if station else (f" in {section}" if section else "")
        return f"{target} has resumed movement{loc} following clearance of the conflicting block. Normal running speed is being restored."

    # Train waiting / manual hold event
    if ev["event_type"] in ("TRAIN_WAITING", "HOLD") or reason_type == "manual_hold":
        target = holds[0] if holds else (selected if selected else (next(iter(ev["allowed_train_ids"])) if ev["allowed_train_ids"] else "The train"))
        loc = f" at {station}" if station else (f" in {section}" if section else "")
        return f"{target} was held{loc} by controller instruction. The train will remain waiting until the section is cleared for departure."

    # Platform unavailable event
    if ev["event_type"] == "PLATFORM_UNAVAILABLE" or reason_type == "platform_unavailable" or "platform" in str(ev.get("reason", "")).lower():
        target = holds[0] if holds else (next(iter(ev["allowed_train_ids"])) if ev["allowed_train_ids"] else "The train")
        st_name = station or "the station"
        return f"{target} was held because no platform was available at {st_name}. The train will remain waiting until a platform becomes available."

    if not selected:
        return ev["reason"] or "RailSync cannot provide a more specific explanation from the available simulation data."

    # Build operational reason clause answering WHY the continuing train was chosen
    if reason_type == "operational_class":
        reason_phrase = f"{selected} is an {ev['winner_type']} train and has higher operational priority in this conflict"
    elif reason_type == "longest_wait":
        reason_phrase = f"{selected} has been waiting the longest"
    elif reason_type == "starvation_safeguard":
        reason_phrase = f"{selected} has been waiting for an extended period, so RailSync gives it priority to prevent prolonged waiting"
    elif reason_type == "higher_predicted_delay":
        reason_phrase = f"{selected} has higher accumulated predicted delay within the same operational class"
    elif reason_type == "deterministic_tiebreak":
        reason_phrase = f"{selected} has timetable precedence in this section"
    else:
        reason_phrase = ev["reason"].rstrip(".") if ev["reason"] else f"{selected} has higher operational priority"

    holds_str = ", ".join(holds) if holds else ""
    plural_was = "was" if len(holds) == 1 else "were"
    plural_is = "is" if len(holds) == 1 else "are"
    conflict_ref = "its movement" if len(holds) == 1 else "their movements"

    # Controller Approval / Rejection
    if action == "approved":
        text = f"{selected} was recommended to continue because {reason_phrase}."
        if holds:
            text += f" {holds_str} {plural_was} recommended to wait because {conflict_ref} conflicted with {selected}."
        text += " The controller approved the recommendation and the hold was applied."
        return text
    elif action == "rejected":
        text = f"{selected} was recommended to continue."
        if holds:
            text += f" {holds_str} {plural_was} recommended to wait."
        text += " The controller rejected the recommendation, so no hold was applied by this recommendation."
        return text

    # Active conflict recommendation: explains WHY selected proceeds and WHY others wait
    if conflict_type == "active":
        loc = f" in {section}" if section else ""
        if holds:
            return (
                f"{reason_phrase}, so RailSync recommends allowing it to continue first{loc}. "
                f"{holds_str} {plural_is} recommended to wait while the conflicting movement is resolved."
            )
        return f"{reason_phrase}, so RailSync recommends allowing it to continue first{loc}."

    # Projected conflict recommendation
    loc = f" in {section}" if section else ""
    overlap_phrase = (
        f"; the projected section overlap is about {ev['overlap_minutes']} minutes"
        if ev.get("overlap_minutes") is not None
        else ""
    )
    if holds:
        return (
            f"{selected} and {holds_str} are expected to use the same logical section{loc} at overlapping times{overlap_phrase}. "
            f"{reason_phrase}, so RailSync recommends allowing it to continue first. "
            f"{holds_str} {plural_is} recommended to wait while the conflict is resolved."
        )
    return f"{reason_phrase}, so RailSync recommends allowing it to continue first{loc}{overlap_phrase}."


# Backwards compatibility alias for existing callers
build_log_fallback = build_deterministic_fallback


def validate_explanation(text: str, context: dict) -> bool:
    """Validate MiniMax output against authoritative decision evidence."""
    if not text or not isinstance(text, str):
        return False

    normalized = text.lower()
    words = text.split()
    if len(words) < 2 or len(words) > 120:
        return False

    # Prohibited claims, internal terminology, and safety violations
    prohibited_terms = (
        "deterministic train-number tie-breaker",
        "train-number tie-breaker",
        "tie-breaker",
        "tiebreaker",
        "operational_class",
        "starvation safeguard",
        "starvation_safeguard",
        "priority score",
        "decision_id",
        "decision id",
        "event_id",
        "event id",
        "projected occupancy window",
        "occupancy window",
        "model feature",
        "feature importance",
        "xgboost prediction",
        "xgboost",
        "algorithm",
        "heuristic",
        "collision",
        "crash",
        "head-on",
        "derailment",
        "smash",
        "catastrophe",
        "signalling aspect",
        "signal aspect",
        "signal violation",
        "red signal",
        "yellow signal",
        "green signal",
        "physical track",
        "double track",
        "single track line",
        "speed limit",
        "passenger count",
        "passengers on board",
        "weather",
        "equipment failure",
        "brake failure",
        "engine failure",
        "guarantee safety",
        "guarantees safety",
        "guarantee railway safety",
        "guarantees railway safety",
        "certified safe",
    )
    if any(term in normalized for term in prohibited_terms):
        return False

    if re.search(r"\bguarantees?\b.*\bsafety\b", normalized):
        return False

    # Check for exposed mathematical formulas/scores like "score of 30" or "0.83 beats"
    if (
        re.search(r"\bscore\s*=\s*\d+", normalized)
        or re.search(r"\bscore of \d+", normalized)
        or re.search(r"\b\d+\.\d+\s+beats\b", normalized)
    ):
        return False

    ev = _normalize_evidence(context)
    allowed_trains = ev["allowed_train_ids"]

    # Verify train IDs: no unmentioned / invented train numbers
    mentioned_trains = set(re.findall(r"\bT\d+(?:-\d+)?\b", text))
    if not mentioned_trains.issubset(allowed_trains):
        return False

    selected = ev["selected_train"]
    holds = set(ev["hold_trains"])
    if selected and selected not in mentioned_trains:
        return False
    if holds and not holds.issubset(mentioned_trains):
        return False

    # Conflict status check
    if ev["conflict_type"] == "projected" and not any(w in normalized for w in ("expected", "projected", "forecast", "ahead", "overlap", "overlapping")):
        return False
    if ev["conflict_type"] == "active" and any(w in normalized for w in ("projected overlap", "forecast to overlap", "expected to enter")):
        return False

    # Controller action check
    action = ev["controller_action"]
    if action == "approved":
        if not ("approv" in normalized or "applied" in normalized):
            return False
    elif action == "rejected":
        if not any(w in normalized for w in ("reject", "no hold", "not applied")):
            return False
        if "hold was applied" in normalized and "no hold was applied" not in normalized:
            return False

    return True


# Backwards compatibility alias
validate_log_explanation = validate_explanation


def narrate_decision(context: dict, fallback: str | None = None, system_prompt: str = SYSTEM_PROMPT) -> dict:
    """Generate a validated natural-language explanation using MiniMax.

    Falls back deterministically to evidence-based explanation if MiniMax is unavailable.
    This function only narrates already-decided deterministic evidence.
    Authoritative decisions (winner_train, held_trains, action, decision_id) are immutable.
    """
    ev_fallback = build_deterministic_fallback(context) if not fallback or any(term in fallback.lower() for term in ("configured operating policy", "<->", "based on its configured")) else fallback
    if not ev_fallback or not ev_fallback.strip():
        ev_fallback = "RailSync cannot provide a more specific explanation from the available simulation data."

    provider = os.getenv("LLM_PROVIDER", "auto").lower()
    if provider == "disabled":
        return {
            "explanation": ev_fallback,
            "source": "deterministic_fallback",
            "fallback_reason": "LLM disabled",
        }

    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    minimax_key = os.getenv("MINIMAX_API_KEY")

    if provider == "auto":
        providers = []
        if minimax_key:
            providers.append("minimax")
        if openrouter_key:
            providers.append("openrouter")
        if not providers:
            providers.append("ollama")
    else:
        providers = [provider]

    validation_rejected = False
    for selected_provider in providers:
        if time.monotonic() < _unavailable_until.get(selected_provider, 0.0):
            continue

        narrated = None
        if selected_provider == "minimax" and minimax_key:
            narrated = _narrate_with_minimax_direct(context, minimax_key, system_prompt)
        elif selected_provider == "openrouter" and openrouter_key:
            narrated = _narrate_with_openrouter(context, openrouter_key, system_prompt)
        elif selected_provider == "ollama":
            narrated = _narrate_with_ollama(context, system_prompt)

        if narrated:
            if validate_explanation(narrated, context):
                return {
                    "explanation": narrated,
                    "source": selected_provider,
                    "fallback_reason": None,
                }
            validation_rejected = True

    return {
        "explanation": ev_fallback,
        "source": "deterministic_fallback",
        "fallback_reason": "LLM rejected" if validation_rejected else "LLM unavailable",
    }


def narrate_log_event(context: dict) -> dict:
    """Generate a validated natural-language explanation for operational log events."""
    fallback = build_deterministic_fallback(context)
    return narrate_decision(context, fallback, system_prompt=LOG_SYSTEM_PROMPT)


def _narrate_with_openrouter(context: dict, api_key: str, system_prompt: str = SYSTEM_PROMPT) -> str | None:
    model = os.getenv("OPENROUTER_MODEL", "minimax/minimax-m3:free")
    try:
        response = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost:8000",
                "X-Title": "RailSync",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(context, sort_keys=True)},
                ],
                "max_tokens": 140,
                "temperature": 0.2,
                "reasoning": {"enabled": False},
            },
            timeout=OPENROUTER_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
        msg = data["choices"][0]["message"]
        narrated = (msg.get("content") or "").strip()
        return narrated or None
    except Exception as e:
        _unavailable_until["openrouter"] = time.monotonic() + RETRY_COOLDOWN_SECONDS
        print(f"[llm_narration] OpenRouter MiniMax unavailable ({e})")
        return None


def _narrate_with_minimax_direct(context: dict, api_key: str, system_prompt: str = SYSTEM_PROMPT) -> str | None:
    model = os.getenv("MINIMAX_MODEL", "MiniMax-Text-01")
    url = os.getenv("MINIMAX_API_URL", MINIMAX_DIRECT_URL)
    try:
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(context, sort_keys=True)},
                ],
                "max_tokens": 140,
                "temperature": 0.2,
            },
            timeout=MINIMAX_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
        msg = data["choices"][0]["message"]
        narrated = (msg.get("content") or "").strip()
        return narrated or None
    except Exception as e:
        _unavailable_until["minimax"] = time.monotonic() + RETRY_COOLDOWN_SECONDS
        print(f"[llm_narration] Direct MiniMax unavailable ({e})")
        return None


def _narrate_with_ollama(context: dict, system_prompt: str = SYSTEM_PROMPT) -> str | None:
    try:
        response = requests.post(
            os.getenv("OLLAMA_URL", OLLAMA_URL),
            json={
                "model": os.getenv("OLLAMA_MODEL", "gemma3:4b"),
                "prompt": f"{system_prompt}\n\nAuthoritative system data:\n{json.dumps(context, sort_keys=True)}",
                "stream": False,
                "options": {"temperature": 0.2},
            },
            timeout=min(OLLAMA_TIMEOUT_SECONDS, 3),
        )
        response.raise_for_status()
        narrated = response.json().get("response", "").strip()
        return narrated or None
    except Exception as e:
        _unavailable_until["ollama"] = time.monotonic() + RETRY_COOLDOWN_SECONDS
        print(f"[llm_narration] Ollama unavailable ({e})")
        return None
