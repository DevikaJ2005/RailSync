"""Generate reproducible, synthetic RailSync delay-prediction datasets.

The records represent a train at the start of a section in the simulated
Tamil Nadu network. Every model feature is available before the train reaches
the destination; ``delay_min`` is the synthetic arrival-delay outcome for that
section. The data is intentionally synthetic because no verified historical
Indian Railways movement dataset is bundled with this project.

Run from the repository root:
    python datasets/generate_dataset.py

Outputs are written beside this script by default. Use ``--output-dir`` to
write a separate reproducible copy elsewhere.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.delay_features import (  # noqa: E402
    CATEGORICAL_COLUMNS,
    NUMERIC_COLUMNS,
    TARGET_COLUMN,
    calculate_congestion_level,
)
from app.network import STATIONS, TRAINS, get_distance, get_section  # noqa: E402


DEFAULT_SEED = 42
DEFAULT_START_DATE = datetime(2026, 1, 1)
DEFAULT_RECORDS_PER_DAY = 100
DEFAULT_TRAIN_DAYS = 120
DEFAULT_VALIDATION_DAYS = 30
DEFAULT_TEST_DAYS = 30

FULL_COLUMNS = [
    "dataset_split",
    "trip_id",
    "train_no",
    "train_name",
    "train_type",
    "section_id",
    "origin_station",
    "destination_station",
    "scheduled_departure",
    "scheduled_arrival",
    "actual_departure",
    "actual_arrival",
    "day_of_week",
    *NUMERIC_COLUMNS,
    "is_cancelled",
    "conflict_flag",
    TARGET_COLUMN,
]


def _sample_scheduled_departure(rng: np.random.Generator, start_date: datetime, days: int) -> datetime:
    """Sample a timetable-like departure, with more services in peak periods."""

    peak_hours = np.array([7, 8, 9, 17, 18, 19, 20])
    hour = int(rng.choice(peak_hours)) if rng.random() < 0.47 else int(rng.integers(0, 24))
    return start_date + timedelta(
        days=int(rng.integers(0, days)),
        hours=hour,
        minutes=int(rng.integers(0, 60)),
    )


def _demand_pressure(hour: int, day_of_week: str) -> float:
    if hour in {7, 8, 9, 17, 18, 19, 20}:
        pressure = 1.0
    elif 10 <= hour <= 16:
        pressure = 0.62
    else:
        pressure = 0.30
    if day_of_week in {"Saturday", "Sunday"}:
        pressure *= 0.82
    return pressure


def _sample_operational_context(
    rng: np.random.Generator,
    hour: int,
    day_of_week: str,
    destination: str,
) -> dict:
    """Generate state that an operations system could observe pre-arrival."""

    pressure = _demand_pressure(hour, day_of_week)
    platform_count = int(STATIONS[destination]["platforms"])
    section_occupancy = min(5, int(rng.poisson(0.18 + 1.65 * pressure)))
    nearby_train_count = min(
        10,
        section_occupancy + int(rng.poisson(0.30 + 2.30 * pressure)),
    )

    platform_busy_probability = min(
        0.97,
        0.15 + 0.57 * pressure + 0.05 * min(nearby_train_count, 5),
    )
    occupied_platforms = int(rng.binomial(platform_count, platform_busy_probability))
    available_platforms = platform_count - occupied_platforms
    occupancy_ratio = occupied_platforms / platform_count

    base_congestion = calculate_congestion_level(
        hour,
        section_occupancy,
        nearby_train_count,
        occupancy_ratio,
    )
    # This is an observed instantaneous traffic measurement, not a hidden
    # outcome. It makes the synthetic signal less perfectly deterministic.
    congestion_level = round(float(np.clip(base_congestion + rng.normal(0, 0.055), 0, 1)), 2)

    headway_minutes = round(
        max(0.5, rng.gamma(shape=2.2, scale=max(1.0, 7.0 - 3.4 * pressure))),
        1,
    )
    required_headway = 4.0 + 0.6 * min(section_occupancy, 3)
    section_conflict = section_occupancy >= 1 and headway_minutes < required_headway
    platform_conflict = available_platforms == 0 and rng.random() < (0.18 + 0.32 * pressure)

    return {
        "section_occupancy": section_occupancy,
        "nearby_train_count": nearby_train_count,
        "destination_platform_occupancy_ratio": round(occupancy_ratio, 3),
        "destination_platform_available_count": available_platforms,
        "congestion_level": congestion_level,
        "conflict_flag": int(section_conflict or platform_conflict),
    }


def _remaining_stops(train: dict, route_index: int) -> int:
    stops_at = set(train.get("stops_at", train["route"]))
    return sum(station in stops_at for station in train["route"][route_index + 1 :])


def _make_row(
    rng: np.random.Generator,
    trip_number: int,
    split_name: str,
    start_date: datetime,
    days: int,
) -> dict:
    train = TRAINS[int(rng.integers(0, len(TRAINS)))]
    route_index = int(rng.integers(0, len(train["route"]) - 1))
    origin = train["route"][route_index]
    destination = train["route"][route_index + 1]
    section = get_section(origin, destination)
    if section is None:
        raise ValueError(f"Backend network has no section for {origin} -> {destination}")

    scheduled_departure = _sample_scheduled_departure(rng, start_date, days)
    hour = scheduled_departure.hour
    day_of_week = scheduled_departure.strftime("%A")
    context = _sample_operational_context(rng, hour, day_of_week, destination)

    nominal_speed = float(train["speed_kmph"])
    speed_spread = {"Express": 5.5, "Passenger": 4.5, "Freight": 3.5}[train["type"]]
    speed_kmph = round(max(20.0, rng.normal(nominal_speed, speed_spread)), 1)
    distance_km = float(get_distance(origin, destination))
    remaining_stops = _remaining_stops(train, route_index)
    prior_delay_min = round(max(0.0, rng.gamma(shape=1.7, scale=3.2) - 1.2), 1)

    type_base_delay = {"Express": 4.5, "Passenger": 7.5, "Freight": 12.0}[train["type"]]
    peak_effect = 1.6 if hour in {7, 8, 9, 17, 18, 19, 20} else 0.0
    conflict_effect = 2.2 if context["conflict_flag"] else 0.0
    # An occasional unobserved incident gives the model a realistic residual;
    # it is never written as an input feature and therefore cannot leak.
    disruption = float(rng.gamma(shape=1.8, scale=2.2)) if rng.random() < 0.19 else 0.0
    random_variation = float(rng.normal(0, 3.2))
    delay_min = max(
        0.0,
        type_base_delay
        + 0.53 * prior_delay_min
        + 8.2 * context["congestion_level"]
        + 1.25 * context["section_occupancy"]
        + 0.38 * context["nearby_train_count"]
        + 4.0 * context["destination_platform_occupancy_ratio"]
        + (2.8 if context["destination_platform_available_count"] == 0 else 0.0)
        + 0.018 * distance_km
        + 0.48 * remaining_stops
        + peak_effect
        + conflict_effect
        + disruption
        + random_variation,
    )
    delay_min = round(delay_min, 1)

    cancellation_probability = (
        0.006
        + (0.014 if context["congestion_level"] > 0.82 else 0.0)
        + (0.020 if context["conflict_flag"] else 0.0)
        + (0.009 if train["type"] == "Freight" else 0.0)
    )
    is_cancelled = int(rng.random() < cancellation_probability)

    scheduled_runtime_minutes = max(5, round(distance_km / nominal_speed * 60))
    scheduled_arrival = scheduled_departure + timedelta(minutes=scheduled_runtime_minutes)
    actual_departure = scheduled_departure + timedelta(minutes=prior_delay_min)
    actual_arrival = scheduled_arrival + timedelta(minutes=delay_min)

    if is_cancelled:
        delay_value = None
        actual_departure_value = None
        actual_arrival_value = None
    else:
        delay_value = delay_min
        actual_departure_value = actual_departure.strftime("%Y-%m-%d %H:%M")
        actual_arrival_value = actual_arrival.strftime("%Y-%m-%d %H:%M")

    return {
        "dataset_split": split_name,
        "trip_id": f"{split_name[:3].upper()}-{trip_number:07d}",
        "train_no": train["train_no"],
        "train_name": train["name"],
        "train_type": train["type"],
        "section_id": section["id"],
        "origin_station": origin,
        "destination_station": destination,
        "scheduled_departure": scheduled_departure.strftime("%Y-%m-%d %H:%M"),
        "scheduled_arrival": scheduled_arrival.strftime("%Y-%m-%d %H:%M"),
        "actual_departure": actual_departure_value,
        "actual_arrival": actual_arrival_value,
        "hour_of_day": hour,
        "day_of_week": day_of_week,
        "section_distance_km": distance_km,
        "remaining_stops": remaining_stops,
        "speed_kmph": speed_kmph,
        "prior_delay_min": prior_delay_min,
        **context,
        "is_cancelled": is_cancelled,
        "delay_min": delay_value,
    }


def generate_split(
    rng: np.random.Generator,
    split_name: str,
    start_date: datetime,
    days: int,
    records_per_day: int,
    first_trip_number: int,
) -> pd.DataFrame:
    rows = [
        _make_row(rng, first_trip_number + index, split_name, start_date, days)
        for index in range(days * records_per_day)
    ]
    return pd.DataFrame(rows, columns=FULL_COLUMNS).sort_values("scheduled_departure").reset_index(drop=True)


def _write_split(frame: pd.DataFrame, split_name: str, output_dir: Path) -> tuple[Path, Path]:
    full_path = output_dir / f"{split_name}_dataset_full.csv"
    model_ready_path = output_dir / f"{split_name}_dataset_model_ready.csv"
    frame.to_csv(full_path, index=False)
    frame.loc[frame["is_cancelled"] == 0].reset_index(drop=True).to_csv(model_ready_path, index=False)
    return full_path, model_ready_path


def _print_summary(frame: pd.DataFrame, split_name: str) -> None:
    model_ready = frame.loc[frame["is_cancelled"] == 0]
    print(
        f"{split_name.title():10} full={len(frame):5,} | model-ready={len(model_ready):5,} | "
        f"cancellations={frame['is_cancelled'].mean():.2%} | "
        f"conflict flags={frame['conflict_flag'].mean():.2%}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate synthetic RailSync datasets.")
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--records-per-day", type=int, default=DEFAULT_RECORDS_PER_DAY)
    parser.add_argument("--train-days", type=int, default=DEFAULT_TRAIN_DAYS)
    parser.add_argument("--validation-days", type=int, default=DEFAULT_VALIDATION_DAYS)
    parser.add_argument("--test-days", type=int, default=DEFAULT_TEST_DAYS)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if min(args.records_per_day, args.train_days, args.validation_days, args.test_days) <= 0:
        raise ValueError("All split sizes must be positive.")

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(args.seed)

    validation_start = DEFAULT_START_DATE + timedelta(days=args.train_days)
    test_start = validation_start + timedelta(days=args.validation_days)
    split_specs = [
        ("train", DEFAULT_START_DATE, args.train_days),
        ("validation", validation_start, args.validation_days),
        ("test", test_start, args.test_days),
    ]

    trip_number = 1
    generated = {}
    for split_name, start_date, days in split_specs:
        frame = generate_split(
            rng,
            split_name,
            start_date,
            days,
            args.records_per_day,
            trip_number,
        )
        trip_number += len(frame)
        generated[split_name] = frame
        _write_split(frame, split_name, output_dir)
        _print_summary(frame, split_name)

    print(f"\nWrote datasets to: {output_dir}")
    print(f"Delay-model categorical columns: {', '.join(CATEGORICAL_COLUMNS)}")
    print(f"Delay-model numeric columns: {', '.join(NUMERIC_COLUMNS)}")
    print(f"Target: {TARGET_COLUMN}")
    print(
        "Split policy: chronological non-overlapping periods "
        f"({generated['train']['scheduled_departure'].min()} through "
        f"{generated['test']['scheduled_departure'].max()})."
    )


if __name__ == "__main__":
    main()
