"""Produce deterministic, explainable recommendations for simulated conflicts.

The simulator's generic ``priority_score`` remains useful for queue ordering.
Conflict recommendations use a separate class-first policy so an unbounded
predicted delay cannot silently outweigh a train's configured class.
"""

from __future__ import annotations


CONFLICT_CLASS_RANK = {"Express": 3, "Passenger": 2, "Freight": 1}
STARVATION_WAIT_MINUTES = 15.0


def resolve_conflicts(conflicts: list, sim_state: dict) -> list:
    trains_by_no = {t["train_no"]: t for t in sim_state["trains"]}
    resolutions = []

    for conflict in _coalesce_projected_conflicts(conflicts):
        involved = [trains_by_no[no] for no in conflict["trains_involved"] if no in trains_by_no]
        if len(involved) < 2:
            continue

        ranked, selection_rule = _rank_for_conflict(involved)
        winner = ranked[0]
        held, unaffected, hold_reasons = _select_interventions(winner, involved, conflict)
        decision_evidence = _decision_evidence(winner, held, unaffected, hold_reasons, involved, conflict, selection_rule)
        reason = _build_reason(winner, held, unaffected, hold_reasons, conflict, selection_rule)

        decision_id = f"{conflict['section']}|{winner['train_no']}|{','.join(h['train_no'] for h in held)}"
        resolutions.append({
            "conflict_id": conflict.get("conflict_id"),
            "event_id": conflict.get("event_id"),
            "conflict_status": conflict.get("conflict_status", "active"),
            "overlap_label": conflict.get("overlap_label"),
            "direction_relation": conflict.get("direction_relation", "unknown"),
            "train_movements": conflict.get("train_movements", {}),
            "risk": conflict.get("risk", "MEDIUM"),
            "decision_id": decision_id,
            "section": conflict["section"],
            "winner_train": winner["train_no"],
            "held_trains": [h["train_no"] for h in held],
            "unaffected_trains": [train["train_no"] for train in unaffected],
            "action": "proceed",
            "reason": reason,
            "decision_evidence": decision_evidence,
            "resolved_by": "simulation",
            "approval_status": "pending",
            "severity": conflict["severity"],
            "affected_trains": len(involved),
            "max_predicted_delay": round(conflict["max_predicted_delay"], 1),
            "winner_predicted_delay_min": round(winner["predicted_delay_min"], 1),
            # Retained as a simulator queue metric, not the conflict decision score.
            "winner_priority_score": winner["priority_score"],
            "held_priority_scores": {h["train_no"]: h["priority_score"] for h in held},
            "estimated_hold_minutes": _estimate_hold_minutes(winner),
            "priority_breakdown": winner.get("priority_breakdown", {}),
            "predicted_arrivals": conflict.get("predicted_arrivals", {}),
            "expected_overlap_minutes": conflict.get("expected_overlap_minutes"),
            "train_predictions": {
                train["train_no"]: {
                    "predicted_delay_min": round(train["predicted_delay_min"], 1),
                    "prediction_context": train.get("prediction_context", {}),
                }
                for train in involved
            },
        })

    return resolutions


def _coalesce_projected_conflicts(conflicts: list[dict]) -> list[dict]:
    """Resolve one recommendation for overlapping projected conflict episodes.

    Pairwise forecasts that share a train and overlap in time are one decision
    episode, not separate instructions. Active conflicts and unrelated windows
    remain unchanged.
    """

    merged = []
    for conflict in conflicts:
        if conflict.get("conflict_status") != "predicted":
            merged.append(conflict)
            continue

        matching = next(
            (candidate for candidate in merged
             if candidate.get("conflict_status") == "predicted"
             and candidate.get("section") == conflict.get("section")
             and set(candidate.get("trains_involved", [])) & set(conflict.get("trains_involved", []))
             and _projected_conflicts_overlap(candidate, conflict)),
            None,
        )
        if matching is None:
            merged.append(dict(conflict))
            continue

        _merge_projected_conflict(matching, conflict)

    return merged


def _projected_conflicts_overlap(left: dict, right: dict) -> bool:
    left_windows = left.get("projected_windows", {})
    right_windows = right.get("projected_windows", {})
    shared = set(left_windows) & set(right_windows)
    if not shared:
        return False
    return any(
        min(left_windows[train_no]["exit_minutes"], right_windows[train_no]["exit_minutes"])
        >= max(left_windows[train_no]["entry_minutes"], right_windows[train_no]["entry_minutes"])
        for train_no in shared
    )


def _merge_projected_conflict(target: dict, incoming: dict) -> None:
    target["trains_involved"] = sorted(set(target.get("trains_involved", [])) | set(incoming.get("trains_involved", [])))
    target["conflicting_pairs"] = _unique_pairs(target.get("conflicting_pairs", []) + incoming.get("conflicting_pairs", []))
    target["train_movements"] = {**target.get("train_movements", {}), **incoming.get("train_movements", {})}
    target["predicted_arrivals"] = {**target.get("predicted_arrivals", {}), **incoming.get("predicted_arrivals", {})}
    target["projected_windows"] = {**target.get("projected_windows", {}), **incoming.get("projected_windows", {})}
    target["max_predicted_delay"] = max(target.get("max_predicted_delay", 0), incoming.get("max_predicted_delay", 0))
    target["expected_overlap_minutes"] = max(target.get("expected_overlap_minutes", 0), incoming.get("expected_overlap_minutes", 0))
    if target.get("risk") != "HIGH" and incoming.get("risk") == "HIGH":
        target["risk"] = "HIGH"
        target["severity"] = "major"
    target["conflict_id"] = f"{target['section']}|{','.join(target['trains_involved'])}"
    target["event_id"] = f"projected|{target['conflict_id']}"


def _unique_pairs(pairs: list) -> list[list[str]]:
    unique = {tuple(sorted(pair)) for pair in pairs if len(pair) >= 2}
    return [list(pair) for pair in sorted(unique)]


def _select_interventions(winner: dict, involved: list[dict], conflict: dict) -> tuple[list[dict], list[dict], dict]:
    """Hold only participants with an explicit relationship to the winner.

    Detector output contains exact pair relationships. A legacy two-train
    payload remains resolvable, while larger relationship-less groups are not
    converted into an implicit "hold everyone else" recommendation.
    """

    train_by_no = {train["train_no"]: train for train in involved}
    winner_no = winner["train_no"]
    pairs = conflict.get("conflicting_pairs")
    if pairs is None:
        pairs = conflict.get("conflict_pairs")

    if pairs is None and len(involved) == 2:
        pairs = [[winner_no, next(train_no for train_no in train_by_no if train_no != winner_no)]]

    related_train_numbers = set()
    for pair in pairs or []:
        if isinstance(pair, dict):
            pair = pair.get("trains") or pair.get("train_numbers") or []
        if winner_no in pair:
            related_train_numbers.update(train_no for train_no in pair if train_no != winner_no)

    held = [train for train in involved if train["train_no"] in related_train_numbers]
    unaffected = [train for train in involved if train["train_no"] not in related_train_numbers and train["train_no"] != winner_no]
    hold_reasons = {
        train["train_no"]: _hold_reason(winner, train, conflict)
        for train in held
    }
    return held, unaffected, hold_reasons


def _hold_reason(winner: dict, held: dict, conflict: dict) -> str:
    overlap = conflict.get("expected_overlap_minutes")
    if overlap is not None:
        return f"{held['train_no']} has a projected movement overlap with {winner['train_no']} ({overlap} minutes)."
    return f"{held['train_no']} shares the currently occupied logical section with {winner['train_no']}."


def _rank_for_conflict(trains: list[dict]) -> tuple[list[dict], str]:
    """Apply the class-first policy, with an explicit starvation safeguard."""

    starved = [train for train in trains if _minutes_waited(train) >= STARVATION_WAIT_MINUTES]
    if starved:
        ranked_starved = sorted(starved, key=_starvation_key, reverse=True)
        remaining = [train for train in trains if train not in starved]
        return ranked_starved + sorted(remaining, key=_class_key, reverse=True), "starvation_safeguard"
    return sorted(trains, key=_class_key, reverse=True), "operational_class"


def _class_key(train: dict) -> tuple:
    """Class is primary; wait and delay only compare trains in the same class."""

    return (
        _class_rank(train),
        _minutes_waited(train),
        max(0.0, float(train.get("predicted_delay_min", 0.0))),
        _tiebreak(train),
    )


def _starvation_key(train: dict) -> tuple:
    return (
        _minutes_waited(train),
        _class_rank(train),
        max(0.0, float(train.get("predicted_delay_min", 0.0))),
        _tiebreak(train),
    )


def _class_rank(train: dict) -> int:
    return CONFLICT_CLASS_RANK.get(train.get("type"), 0)


def _minutes_waited(train: dict) -> float:
    return max(0.0, float(train.get("minutes_waited", 0.0)))


def _tiebreak(train: dict) -> float:
    breakdown = train.get("priority_breakdown", {})
    if "tiebreak" in breakdown:
        return float(breakdown["tiebreak"])
    return int("".join(filter(str.isdigit, train["train_no"])) or 0) * 0.001


def _train_evidence(train: dict) -> dict:
    return {
        "train_no": train["train_no"],
        "train_type": train.get("type", "Unknown"),
        "operational_class_rank": _class_rank(train),
        "predicted_delay_min": round(float(train.get("predicted_delay_min", 0.0)), 1),
        "current_delay_min": round(float(train.get("current_delay_min", train.get("prior_delay_min", 0.0))), 1),
        "minutes_waited": round(_minutes_waited(train), 1),
        "queue_priority_score": train.get("priority_score"),
        "deterministic_tiebreak": round(_tiebreak(train), 3),
    }


def _determine_reason_type(winner: dict, held: list[dict], selection_rule: str) -> tuple[str, str]:
    if selection_rule == "starvation_safeguard":
        return "starvation_safeguard", f"{winner['train_no']} has been waiting for an extended period and receives priority to prevent prolonged waiting"
    highest_held_class = max((_class_rank(train) for train in held), default=-1)
    if _class_rank(winner) > highest_held_class:
        return "operational_class", f"{winner['train_no']} is an {winner.get('type', 'Unknown')} train and has higher operational priority in this conflict"
    if any(_minutes_waited(winner) > _minutes_waited(train) for train in held):
        return "longest_wait", f"{winner['train_no']} has been waiting the longest in this conflict"
    if any(float(winner.get("predicted_delay_min", 0.0)) > float(train.get("predicted_delay_min", 0.0)) for train in held):
        return "higher_predicted_delay", f"{winner['train_no']} has higher accumulated predicted delay within the same operational class"
    return "deterministic_tiebreak", f"{winner['train_no']} has timetable precedence within the same operational class"


def _decision_evidence(winner: dict, held: list[dict], unaffected: list[dict], hold_reasons: dict, participants: list[dict], conflict: dict, selection_rule: str) -> dict:
    overlap = conflict.get("expected_overlap_minutes")
    reason_type, operational_summary = _determine_reason_type(winner, held, selection_rule)
    conflict_type = "predicted" if conflict.get("conflict_status") == "predicted" else "active"
    trains_profiles = [
        {
            "train_id": train["train_no"],
            "status": "Waiting" if train.get("status") in ("waiting", "held") or _minutes_waited(train) > 0 else "Moving",
            "train_type": train.get("type", "Unknown"),
            "waiting_minutes": round(_minutes_waited(train), 1),
            "predicted_delay_min": round(float(train.get("predicted_delay_min", 0.0)), 1),
        }
        for train in participants
    ]
    return {
        "policy": "class_first_starvation_aware",
        "selection_rule": selection_rule,
        "reason_type": reason_type,
        "operational_summary": operational_summary,
        "conflict_type": conflict_type,
        "section": conflict.get("section", ""),
        "selection_order": (
            ["waiting_time", "operational_class", "predicted_delay", "deterministic_tiebreak"]
            if selection_rule == "starvation_safeguard"
            else ["operational_class", "waiting_time_within_class", "predicted_delay_within_class", "deterministic_tiebreak"]
        ),
        "conflict": {
            "description": "Projected section overlap" if conflict_type == "predicted" else "Current simulated section overlap",
            "participants": [train["train_no"] for train in participants],
            "risk": conflict.get("risk", "MEDIUM"),
            "expected_overlap_minutes": round(float(overlap), 1) if overlap is not None else None,
            "projected_arrivals": conflict.get("predicted_arrivals", {}),
            "direction_relation": conflict.get("direction_relation", "unknown"),
            "train_movements": conflict.get("train_movements", {}),
        },
        "selected_train": winner["train_no"],
        "winner": _train_evidence(winner),
        "held_trains": [_train_evidence(train) for train in held],
        "trains_requiring_hold": [train["train_no"] for train in held],
        "hold_reasons": hold_reasons,
        "unaffected_trains": [train["train_no"] for train in unaffected],
        "trains_involved_profiles": trains_profiles,
    }


def _build_reason(winner: dict, held: list[dict], unaffected: list[dict], hold_reasons: dict, conflict: dict, selection_rule: str) -> str:
    if selection_rule == "starvation_safeguard":
        reason = (
            f"{winner['train_no']} has waited {round(_minutes_waited(winner), 1)} minutes and receives the "
            "configured starvation safeguard for this conflict."
        )
    else:
        highest_held_class = max((_class_rank(train) for train in held), default=-1)
        if _class_rank(winner) > highest_held_class:
            basis = f"its configured {winner.get('type', 'Unknown')} class"
        elif any(_minutes_waited(winner) > _minutes_waited(train) for train in held):
            basis = "the longer waiting time within the same operational class"
        elif any(float(winner.get("predicted_delay_min", 0.0)) > float(train.get("predicted_delay_min", 0.0)) for train in held):
            basis = "the higher predicted delay within the same operational class"
        else:
            basis = "the deterministic train-number tie-breaker within the same operational class"

        if conflict.get("conflict_status") == "predicted":
            overlap = conflict.get("expected_overlap_minutes", 0)
            reason = f"{winner['train_no']} has higher operational priority based on {basis}; the projected section overlap is about {overlap} minutes."
        else:
            reason = f"{winner['train_no']} has higher operational priority based on {basis} and proceeds through {conflict['section']}."

    if held:
        reason += " " + " ".join(hold_reasons[train["train_no"]] for train in held)
    if unaffected:
        reason += f" Other trains are not affected by this recommendation."
    return reason


def _estimate_hold_minutes(winner: dict) -> int:
    remaining_fraction = max(0.0, 1.0 - float(winner.get("progress", 0)))
    speed = max(float(winner.get("speed_kmph", 1)), 1.0)
    # Controller display estimate only; exact route distances stay in the simulator.
    return max(2, round(remaining_fraction * 60 / (speed / 60)))
