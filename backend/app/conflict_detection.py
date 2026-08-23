"""
Section-level conflict detection — two or more trains occupying the same
open track segment (between stations) at overlapping times. Separate
from platform conflicts, which are handled directly by PlatformManager.
"""


def detect_section_conflicts(sim_state: dict) -> list:
    trains = sim_state["trains"]
    groups = {}

    for t in trains:
        if t["status"] in ("completed", "at_platform"):
            continue
        key = tuple(sorted([t["from"], t["to"]]))
        if t["from"] == t["to"]:
            continue
        groups.setdefault(key, []).append(t)

    conflicts = []
    for section, group in groups.items():
        if len(group) < 2:
            continue
        max_delay = max(g["predicted_delay_min"] for g in group)
        conflicts.append({
            "section": f"{section[0]} <-> {section[1]}",
            "trains_involved": [g["train_no"] for g in group],
            "severity": "major" if max_delay > 30 else "minor",
            "max_predicted_delay": max_delay,
        })
    return conflicts
