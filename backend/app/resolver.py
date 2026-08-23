"""Produce explainable ML-assisted recommendations for section conflicts."""


def resolve_conflicts(conflicts: list, sim_state: dict) -> list:
    trains_by_no = {t["train_no"]: t for t in sim_state["trains"]}
    resolutions = []

    for conflict in conflicts:
        involved = [trains_by_no[no] for no in conflict["trains_involved"] if no in trains_by_no]
        if len(involved) < 2:
            continue

        ranked = sorted(involved, key=lambda t: t["priority_score"], reverse=True)
        winner, held = ranked[0], ranked[1:]

        reason = _build_reason(winner, held, conflict)

        decision_id = f"{conflict['section']}|{winner['train_no']}|{','.join(h['train_no'] for h in held)}"
        resolutions.append({
            "decision_id": decision_id,
            "section": conflict["section"],
            "winner_train": winner["train_no"],
            "held_trains": [h["train_no"] for h in held],
            "action": "proceed",
            "reason": reason,
            "resolved_by": "ml",
            "approval_status": "pending",
            "severity": conflict["severity"],
            "affected_trains": len(involved),
            "max_predicted_delay": round(conflict["max_predicted_delay"], 1),
            "winner_priority_score": winner["priority_score"],
            "held_priority_scores": {h["train_no"]: h["priority_score"] for h in held},
            "estimated_hold_minutes": _estimate_hold_minutes(winner),
        })

    return resolutions


def _build_reason(winner: dict, held: list, conflict: dict) -> str:
    held_desc = ", ".join(h["train_no"] for h in held)
    parts = [
        f"{winner['train_no']} ({winner['type']}) proceeds through {conflict['section']}"
    ]
    factors = []
    if winner["type"] == "Express":
        factors.append("Express trains have higher base priority")
    if winner["predicted_delay_min"] > 15:
        factors.append(f"it is already {winner['predicted_delay_min']} minutes late")
    if winner.get("minutes_waited", 0) > 5:
        factors.append(f"it has waited {winner['minutes_waited']} minutes")
    if not factors:
        factors.append("it has the highest current priority score")
    if factors:
        parts.append(f"({', '.join(factors)})")
    parts.append(f"So {held_desc} wait. Score: {winner['priority_score']} vs "
                 f"{', '.join(str(h['priority_score']) for h in held)}.")
    return " ".join(parts)


def _estimate_hold_minutes(winner: dict) -> int:
    remaining_fraction = max(0.0, 1.0 - float(winner.get("progress", 0)))
    speed = max(float(winner.get("speed_kmph", 1)), 1.0)
    # Controller display estimate only; exact route distances stay in the simulator.
    return max(2, round(remaining_fraction * 60 / (speed / 60)))
