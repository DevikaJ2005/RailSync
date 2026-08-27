"""Shared, pre-event feature contract for RailSync delay prediction.

The XGBoost model predicts a synthetic train's delay at the end of its
current section.  This module is deliberately independent of the model so
that the dataset generator and the live simulator use one feature schema.
All values must be known at the prediction point; no arrival outcome,
future platform allocation, or final conflict result is included.
"""

from __future__ import annotations

from typing import Mapping

from app.network import get_distance


SCHEMA_VERSION = "2.0"
TARGET_COLUMN = "delay_min"

CATEGORICAL_COLUMNS = [
    "train_type",
    "origin_station",
    "destination_station",
    "day_of_week",
]

NUMERIC_COLUMNS = [
    "hour_of_day",
    "section_distance_km",
    "remaining_stops",
    "speed_kmph",
    "prior_delay_min",
    "section_occupancy",
    "nearby_train_count",
    "destination_platform_occupancy_ratio",
    "destination_platform_available_count",
    "congestion_level",
]

MODEL_FEATURE_COLUMNS = NUMERIC_COLUMNS + [f"{column}_enc" for column in CATEGORICAL_COLUMNS]


def calculate_congestion_level(
    hour_of_day: int,
    section_occupancy: int,
    nearby_train_count: int,
    destination_platform_occupancy_ratio: float,
) -> float:
    """Return a bounded operational-pressure estimate available before arrival.

    It combines the current time window with observed local traffic and the
    destination's current platform pressure.  It is not a delay label and is
    intentionally usable by both synthetic-data generation and the runtime.
    """

    peak_bonus = 0.20 if hour_of_day in {7, 8, 9, 17, 18, 19, 20} else 0.0
    daytime_bonus = 0.06 if 10 <= hour_of_day <= 16 else 0.0
    value = (
        0.12
        + peak_bonus
        + daytime_bonus
        + min(max(section_occupancy, 0), 5) * 0.12
        + min(max(nearby_train_count, 0), 10) * 0.035
        + min(max(destination_platform_occupancy_ratio, 0.0), 1.0) * 0.28
    )
    return round(min(1.0, max(0.0, value)), 2)


def _remaining_stops(train) -> int:
    remaining_route = train.route[train.route_index + 1 :]
    return sum(station in train.stops_at for station in remaining_route)


def build_delay_features(train, sim_time, context: Mapping[str, float | int]) -> dict:
    """Build the exact feature payload consumed by ``predict_delay``.

    ``context`` is produced from the simulator's current state before train
    movement for the tick.  Keeping it explicit makes data provenance easy to
    explain at a hackathon demo.
    """

    origin = train.current_from
    destination = train.current_to
    section_occupancy = int(context.get("section_occupancy", 0))
    nearby_train_count = int(context.get("nearby_train_count", 0))
    platform_ratio = float(context.get("destination_platform_occupancy_ratio", 0.0))

    return {
        "train_type": train.type,
        "origin_station": origin,
        "destination_station": destination,
        "day_of_week": sim_time.strftime("%A"),
        "hour_of_day": int(sim_time.hour),
        "section_distance_km": float(get_distance(origin, destination)),
        "remaining_stops": int(_remaining_stops(train)),
        "speed_kmph": float(train.speed_kmph),
        "prior_delay_min": float(train.prior_delay_min),
        "section_occupancy": section_occupancy,
        "nearby_train_count": nearby_train_count,
        "destination_platform_occupancy_ratio": round(platform_ratio, 3),
        "destination_platform_available_count": int(
            context.get("destination_platform_available_count", 0)
        ),
        "congestion_level": calculate_congestion_level(
            sim_time.hour,
            section_occupancy,
            nearby_train_count,
            platform_ratio,
        ),
    }
