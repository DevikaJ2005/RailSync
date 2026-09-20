"""Historical delay summaries derived from the shipped evaluation observations.

The repository does not contain the raw training table.  These summaries use
the observed actual delays in test_predictions.csv as a transparent reference
set and are labelled as historical context, not as a replacement for model
training data.
"""

from __future__ import annotations

import csv
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path


DATA_PATH = Path(__file__).resolve().parent / "models" / "test_predictions.csv"
_records = []


def _load_records():
    if not DATA_PATH.exists():
        return []
    records = []
    with DATA_PATH.open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            try:
                row["actual_delay_min"] = float(row["actual_delay_min"])
                row["predicted_delay_min"] = float(row["predicted_delay_min"])
                row["scheduled_departure_dt"] = datetime.strptime(row["scheduled_departure"], "%Y-%m-%d %H:%M")
                records.append(row)
            except (KeyError, TypeError, ValueError):
                continue
    return records


_records = _load_records()


def dataset_summary() -> dict:
    return {
        "source": str(DATA_PATH.name),
        "records": len(_records),
        "actual_delay_observations": len(_records),
        "raw_dataset_available": False,
        "note": "Historical context is estimated from shipped observed evaluation records; the raw training table is not included.",
    }


def _mean(values):
    return sum(values) / len(values) if values else 0.0


def _std(values, mean):
    if len(values) < 2:
        return 0.0
    return math.sqrt(sum((value - mean) ** 2 for value in values) / len(values))


def get_pattern(train, sim_time) -> dict:
    route_key = (train.base_train_no, train.current_from, train.current_to)
    matching = [
        row for row in _records
        if (row["train_no"], row["origin_station"], row["destination_station"]) == route_key
    ]
    if not matching:
        matching = [row for row in _records if row["train_no"] == train.base_train_no]

    values = [row["actual_delay_min"] for row in matching]
    recent = sorted(matching, key=lambda row: row["scheduled_departure_dt"])[-30:]
    recent_values = [row["actual_delay_min"] for row in recent]
    typical = _mean(values)
    recent_average = _mean(recent_values)
    current = float(train.prior_delay_min)
    spread = _std(values, typical)
    threshold = max(5.0, spread * 2.0)
    anomalous = bool(values and current > typical + threshold)
    confidence = "High" if len(values) >= 20 else "Medium" if len(values) >= 5 else "Limited"

    if not values:
        pattern = "No matching historical observations"
    elif abs(recent_average - typical) >= 2:
        direction = "higher" if recent_average > typical else "lower"
        pattern = f"Recent observations are {direction} than the typical service delay"
    else:
        pattern = f"Usually delayed about {typical:.1f} min on this route"

    return {
        "historical_average_delay_min": round(typical, 1) if values else None,
        "recent_average_delay_min": round(recent_average, 1) if recent_values else None,
        "historical_sample_count": len(values),
        "prediction_confidence": confidence,
        "historical_pattern": pattern,
        "anomaly": anomalous,
        "anomaly_deviation_min": round(max(0.0, current - typical), 1) if values else None,
        "anomaly_reason": "Observed delay is significantly above the historical pattern" if anomalous else None,
    }
