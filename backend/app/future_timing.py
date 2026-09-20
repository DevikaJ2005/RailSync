"""Authoritative future timing projection for simulated trains.

The delay model predicts the current section only.  For forecasting later
movement, that prediction is carried forward once as a single offset; it is
not treated as a newly predicted delay for every remaining section.
"""

from __future__ import annotations

from app.network import get_distance


def project_section_windows(train: dict) -> list[dict]:
    """Return future section occupancy windows in minutes from the current time.

    ``predicted_delay_min`` is applied exactly once, to completion of the
    current section. Subsequent section windows use normal travel time.
    """

    route = train["route"]
    route_index = int(train["route_index"])
    speed_kmph = max(float(train["speed_kmph"]), 1.0)
    progress = max(0.0, min(1.0, float(train.get("progress", 0.0))))
    forecast_offset = max(0.0, float(train.get("predicted_delay_min", 0.0)))
    elapsed = 0.0
    windows = []

    for index in range(route_index, len(route) - 1):
        station_a = route[index]
        station_b = route[index + 1]
        distance = get_distance(station_a, station_b)
        if not distance:
            continue

        travel_minutes = distance / speed_kmph * 60.0
        if index == route_index:
            travel_minutes *= 1.0 - progress

        entry = elapsed
        exit_time = entry + travel_minutes
        if index == route_index:
            exit_time += forecast_offset
        windows.append({
            "from": station_a,
            "to": station_b,
            "movement_from": station_a,
            "movement_to": station_b,
            "is_current_section": index == route_index,
            "entry_minutes": entry,
            "exit_minutes": exit_time,
        })
        elapsed = exit_time

    return windows


def next_milestone_eta_minutes(train: dict) -> float | None:
    """Return the projected completion time for the train's current section."""

    windows = project_section_windows(train)
    return windows[0]["exit_minutes"] if windows else None
