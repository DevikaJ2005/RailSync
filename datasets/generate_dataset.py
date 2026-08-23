"""
RailSync — Synthetic Tamil Nadu Railway Delay Dataset Generator
Generates realistic per-trip train records for XGBoost delay prediction.

Distributions are informed by publicly reported Indian Railways delay
statistics (avg delay ranges, % on-time, congestion impact) — not copied
from any single real dataset.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

np.random.seed(42)

# ---------------------------------------------------------------------
# 1. Define network: real Tamil Nadu stations/junctions
# ---------------------------------------------------------------------
STATIONS = [
    "Chennai Central",
    "Katpadi Junction",
    "Jolarpettai Junction",
    "Villupuram Junction",
    "Tiruchirapalli Junction",
    "Madurai Junction",
    "Salem Junction",
    "Coimbatore Junction",
]

# Simple linear-ish route sections (edges between stations) — used to derive
# "section" congestion. Not exhaustive, just enough for a small simulated network.
SECTIONS = [
    ("Chennai Central", "Katpadi Junction"),
    ("Katpadi Junction", "Jolarpettai Junction"),
    ("Jolarpettai Junction", "Salem Junction"),
    ("Salem Junction", "Tiruchirapalli Junction"),
    ("Tiruchirapalli Junction", "Madurai Junction"),
    ("Chennai Central", "Villupuram Junction"),
    ("Villupuram Junction", "Tiruchirapalli Junction"),
    ("Salem Junction", "Coimbatore Junction"),
]

# ---------------------------------------------------------------------
# 2. Define trains: 10 trains, mix of passenger/express/freight
# ---------------------------------------------------------------------
TRAINS = [
    {"train_no": "T101", "name": "Chennai-Coimbatore Express", "type": "Express"},
    {"train_no": "T102", "name": "Chennai-Madurai SF", "type": "Express"},
    {"train_no": "T103", "name": "Katpadi Passenger", "type": "Passenger"},
    {"train_no": "T104", "name": "Salem Freight Special", "type": "Freight"},
    {"train_no": "T105", "name": "Trichy-Chennai Express", "type": "Express"},
    {"train_no": "T106", "name": "Villupuram Passenger", "type": "Passenger"},
    {"train_no": "T107", "name": "Coimbatore Freight Corridor", "type": "Freight"},
    {"train_no": "T108", "name": "Madurai-Chennai SF", "type": "Express"},
    {"train_no": "T109", "name": "Jolarpettai Passenger", "type": "Passenger"},
    {"train_no": "T110", "name": "Salem-Trichy Freight", "type": "Freight"},
]

TRAIN_TYPE_BASE_DELAY = {
    # (mean_delay_min, std_dev) — Express fastest/most punctual, Freight slowest
    "Express": (8, 6),
    "Passenger": (14, 9),
    "Freight": (25, 15),
}

# ---------------------------------------------------------------------
# 3. Generate synthetic trip records
# ---------------------------------------------------------------------
def random_time_of_day():
    """Bias generation toward realistic peak/off-peak hours."""
    peak_hours = [7, 8, 9, 17, 18, 19, 20]
    if np.random.rand() < 0.45:
        hour = np.random.choice(peak_hours)
    else:
        hour = np.random.randint(0, 24)
    minute = np.random.randint(0, 60)
    return hour, minute


def congestion_level(hour):
    """Higher congestion during peak hours, moderate otherwise."""
    if hour in [7, 8, 9, 17, 18, 19, 20]:
        return round(np.random.uniform(0.6, 1.0), 2)
    elif hour in [10, 11, 12, 13, 14, 15, 16]:
        return round(np.random.uniform(0.3, 0.7), 2)
    else:
        return round(np.random.uniform(0.0, 0.4), 2)


def generate_rows(n_rows, start_date, days_span):
    rows = []
    for i in range(n_rows):
        train = TRAINS[np.random.randint(0, len(TRAINS))]
        origin, dest = SECTIONS[np.random.randint(0, len(SECTIONS))]

        hour, minute = random_time_of_day()
        day_offset = np.random.randint(0, days_span)
        trip_date = start_date + timedelta(days=int(day_offset))
        scheduled_departure = trip_date.replace(hour=hour, minute=minute)

        num_stops = np.random.randint(1, 8)
        speed_kmph = {
            "Express": np.random.normal(75, 10),
            "Passenger": np.random.normal(45, 8),
            "Freight": np.random.normal(35, 7),
        }[train["type"]]
        speed_kmph = max(15, round(speed_kmph, 1))

        prior_delay = max(0, round(np.random.normal(6, 5), 1))  # delay carried from previous station
        congestion = congestion_level(hour)

        base_mean, base_std = TRAIN_TYPE_BASE_DELAY[train["type"]]

        # Delay model: base by train type + congestion effect + prior delay carry-over
        # + random noise. Roughly linear combination, clipped at 0.
        delay = (
            base_mean
            + congestion * 20          # congestion pushes delay up
            + prior_delay * 0.4        # some carry-over from previous leg
            + (num_stops - 4) * 1.5    # more stops → slightly more delay
            + np.random.normal(0, base_std)
        )
        delay = max(0, round(delay, 1))

        # Cancellation: rare, more likely for freight during high congestion
        cancel_prob = 0.01 + (0.03 if train["type"] == "Freight" else 0.0) + (0.02 if congestion > 0.8 else 0.0)
        is_cancelled = 1 if np.random.rand() < cancel_prob else 0
        if is_cancelled:
            delay = None

        # Conflict flag: derived — high congestion + delay above threshold roughly
        # correlates with a real scheduling conflict in the simulated network.
        conflict_flag = 1 if (not is_cancelled and congestion > 0.75 and delay > 25) else 0

        rows.append({
            "trip_id": f"TRP{i+1:06d}",
            "train_no": train["train_no"],
            "train_name": train["name"],
            "train_type": train["type"],
            "origin_station": origin,
            "destination_station": dest,
            "scheduled_departure": scheduled_departure.strftime("%Y-%m-%d %H:%M"),
            "hour_of_day": hour,
            "day_of_week": scheduled_departure.strftime("%A"),
            "num_stops": num_stops,
            "speed_kmph": speed_kmph,
            "prior_delay_min": prior_delay,
            "congestion_level": congestion,
            "is_cancelled": is_cancelled,
            "conflict_flag": conflict_flag,
            "delay_min": delay,  # TARGET variable for XGBoost regression
        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------
# 4. Generate TRAIN and TEST sets separately (different date ranges,
#    same distributions — mimics real train/test split by time)
# ---------------------------------------------------------------------
train_df = generate_rows(n_rows=8000, start_date=datetime(2026, 1, 1), days_span=60)
test_df = generate_rows(n_rows=2000, start_date=datetime(2026, 3, 15), days_span=15)

# Drop cancelled trips' delay is None — keep is_cancelled flag as a feature,
# but for training the delay-regression model we drop rows with no delay value
train_df_model_ready = train_df.dropna(subset=["delay_min"]).reset_index(drop=True)
test_df_model_ready = test_df.dropna(subset=["delay_min"]).reset_index(drop=True)

# ---------------------------------------------------------------------
# 5. Save outputs
# ---------------------------------------------------------------------
train_df.to_csv("/home/claude/railsync_data/train_dataset_full.csv", index=False)
test_df.to_csv("/home/claude/railsync_data/test_dataset_full.csv", index=False)
train_df_model_ready.to_csv("/home/claude/railsync_data/train_dataset_model_ready.csv", index=False)
test_df_model_ready.to_csv("/home/claude/railsync_data/test_dataset_model_ready.csv", index=False)

print("Train set (full):", train_df.shape)
print("Test set (full):", test_df.shape)
print("Train set (model-ready, no cancellations):", train_df_model_ready.shape)
print("Test set (model-ready, no cancellations):", test_df_model_ready.shape)
print("\nSample rows:")
print(train_df_model_ready.head(5).to_string())
print("\nDelay stats (train):")
print(train_df_model_ready["delay_min"].describe())
print("\nCancellation rate (train):", train_df["is_cancelled"].mean())
print("Conflict rate (train):", train_df_model_ready["conflict_flag"].mean())
