"""Detect simulated active and projected section overlaps.

Section endpoints are undirected in the current network. Ordered train routes
provide movement evidence only; they do not imply track capacity, signaling,
or real-world safety constraints.
"""

from __future__ import annotations

from datetime import datetime
from itertools import combinations

from app.future_timing import project_section_windows


def detect_section_conflicts(sim_state: dict) -> list:
    groups = {}
    for train in sim_state["trains"]:
        if train["status"] in ("completed", "at_platform") or train["from"] == train["to"]:
            continue
        groups.setdefault(tuple(sorted((train["from"], train["to"]))), []).append(train)

    conflicts = []
    for section, group in groups.items():
        if len(group) < 2:
            continue
        section_label = _section_label(section)
        train_numbers = sorted(train["train_no"] for train in group)
        conflict_pairs = [list(pair) for pair in combinations(train_numbers, 2)]
        movements = _movement_evidence(group)
        max_delay = max(train["predicted_delay_min"] for train in group)
        conflicts.append({
            # Preserve the existing UI/controller-facing identity.
            "conflict_id": f"{section_label}|{','.join(train_numbers)}",
            "event_id": _event_id("active", section_label, train_numbers, f"current;{_movement_signature(movements)}"),
            "section": section_label,
            "trains_involved": train_numbers,
            "conflicting_pairs": conflict_pairs,
            "conflict_status": "active",
            "overlap_label": "ACTIVE SECTION OVERLAP",
            "direction_relation": _direction_relation(movements),
            "train_movements": movements,
            "risk": "HIGH" if max_delay > 30 else "MEDIUM",
            "severity": "major" if max_delay > 30 else "minor",
            "max_predicted_delay": max_delay,
        })
    return conflicts


def detect_predictive_conflicts(sim_state: dict) -> list:
    """Forecast overlapping future section windows using current train state."""

    windows = {}
    for train in sim_state["trains"]:
        if train["status"] in ("completed", "held", "waiting"):
            continue
        for window in project_section_windows(train):
            section = tuple(sorted((window["from"], window["to"])))
            windows.setdefault(section, []).append({
                "train": train,
                "entry": window["entry_minutes"],
                "exit": window["exit_minutes"],
                "movement_from": window["movement_from"],
                "movement_to": window["movement_to"],
                "is_current_section": window["is_current_section"],
            })

    active_pairs = _active_pair_keys(sim_state)
    predicted = []
    for section, section_windows in windows.items():
        for left_index, left in enumerate(section_windows):
            for right in section_windows[left_index + 1:]:
                overlap = min(left["exit"], right["exit"]) - max(left["entry"], right["entry"])
                if overlap <= 0:
                    continue

                section_label = _section_label(section)
                train_numbers = sorted((left["train"]["train_no"], right["train"]["train_no"]))
                if left["is_current_section"] and right["is_current_section"] and _pair_key(section_label, train_numbers) in active_pairs:
                    continue

                movements = _movement_evidence((left, right), window_entries=True)
                risk = "HIGH" if overlap >= 10 else "MEDIUM" if overlap >= 4 else "LOW"
                projected_arrivals = {
                    left["train"]["train_no"]: _format_eta(sim_state["sim_time"], left["entry"]),
                    right["train"]["train_no"]: _format_eta(sim_state["sim_time"], right["entry"]),
                }
                projected_windows = {
                    left["train"]["train_no"]: {
                        "entry_minutes": round(left["entry"], 3),
                        "exit_minutes": round(left["exit"], 3),
                    },
                    right["train"]["train_no"]: {
                        "entry_minutes": round(right["entry"], 3),
                        "exit_minutes": round(right["exit"], 3),
                    },
                }
                window_signature = f"{_window_signature((left, right))};{_movement_signature(movements)}"
                predicted.append({
                    "conflict_id": f"{section_label}|{','.join(train_numbers)}",
                    "event_id": _event_id("projected", section_label, train_numbers, window_signature),
                    "section": section_label,
                    "trains_involved": train_numbers,
                    "conflicting_pairs": [train_numbers],
                    "conflict_status": "predicted",
                    "overlap_label": "PROJECTED SECTION OVERLAP",
                    "direction_relation": _direction_relation(movements),
                    "train_movements": movements,
                    "risk": risk,
                    "severity": "major" if risk == "HIGH" else "minor",
                    "max_predicted_delay": round(max(left["train"]["predicted_delay_min"], right["train"]["predicted_delay_min"]), 1),
                    "expected_overlap_minutes": round(overlap, 1),
                    "predicted_arrivals": projected_arrivals,
                    "projected_windows": projected_windows,
                })
    return predicted


def detect_all_conflicts(sim_state: dict) -> list:
    """Return active overlaps plus non-redundant future projected overlaps."""

    return detect_section_conflicts(sim_state) + detect_predictive_conflicts(sim_state)


def _active_pair_keys(sim_state: dict) -> set[str]:
    pairs = set()
    for conflict in detect_section_conflicts(sim_state):
        for pair in combinations(conflict["trains_involved"], 2):
            pairs.add(_pair_key(conflict["section"], pair))
    return pairs


def _section_label(section: tuple[str, str]) -> str:
    return f"{section[0]} <-> {section[1]}"


def _pair_key(section: str, train_numbers) -> str:
    return f"{section}|{','.join(sorted(train_numbers))}"


def _movement_evidence(items, window_entries: bool = False) -> dict:
    movements = {}
    for item in items:
        train = item["train"] if window_entries else item
        movements[train["train_no"]] = {
            "movement_from": item.get("movement_from") if window_entries else train.get("from"),
            "movement_to": item.get("movement_to") if window_entries else train.get("to"),
        }
    return dict(sorted(movements.items()))


def _direction_relation(movements: dict) -> str:
    directions = [(item.get("movement_from"), item.get("movement_to")) for item in movements.values()]
    if len(directions) < 2 or any(not start or not end or start == end for start, end in directions):
        return "unknown"
    return "same_direction" if len(set(directions)) == 1 else "opposing_direction"


def _window_signature(windows) -> str:
    values = [(window["train"]["train_no"], window["entry"], window["exit"]) for window in windows]
    return ";".join(f"{train}:{entry:.3f}-{exit:.3f}" for train, entry, exit in sorted(values))


def _movement_signature(movements: dict) -> str:
    return ";".join(
        f"{train}:{movement.get('movement_from')}->{movement.get('movement_to')}"
        for train, movement in sorted(movements.items())
    )


def _event_id(status: str, section: str, train_numbers, window_signature: str) -> str:
    return f"{status}|{section}|{','.join(sorted(train_numbers))}|{window_signature}"


def _format_eta(sim_time: str, offset_minutes: float) -> str:
    value = datetime.fromisoformat(sim_time.replace("Z", "+00:00"))
    from datetime import timedelta

    return (value + timedelta(minutes=offset_minutes)).strftime("%Y-%m-%d %H:%M:%S")
