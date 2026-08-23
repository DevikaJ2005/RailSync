"""
Loads the trained XGBoost model + encoders. If no trained model exists
yet (e.g. you haven't run Colab training and dropped the .pkl files in
yet), falls back to a reasonable heuristic so the rest of the app still
runs correctly while you're setting things up.
"""

import os
from dotenv import load_dotenv

load_dotenv()

MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
MODEL_PATH = os.path.join(MODEL_DIR, "xgb_delay_model.pkl")
ENCODERS_PATH = os.path.join(MODEL_DIR, "label_encoders.pkl")
FEATURES_PATH = os.path.join(MODEL_DIR, "feature_columns.pkl")

CATEGORICAL_COLS = ["train_type", "origin_station", "destination_station", "day_of_week"]
NUMERIC_COLS = ["num_stops", "speed_kmph", "prior_delay_min", "congestion_level", "hour_of_day"]

_model = None
_encoders = None
_feature_cols = None
_loaded = False


def load_model():
    global _model, _encoders, _feature_cols, _loaded
    model_enabled = os.getenv("DELAY_MODEL_ENABLED", "true").lower() in ("1", "true", "yes", "on")
    if not model_enabled:
        _loaded = False
        print("[model_loader] Delay model disabled by DELAY_MODEL_ENABLED; using heuristic fallback.")
        return

    if os.path.exists(MODEL_PATH) and os.path.exists(ENCODERS_PATH) and os.path.exists(FEATURES_PATH):
        import joblib

        _model = joblib.load(MODEL_PATH)
        _encoders = joblib.load(ENCODERS_PATH)
        _feature_cols = joblib.load(FEATURES_PATH)
        _loaded = True
        print("[model_loader] Trained XGBoost model loaded.")
    else:
        _loaded = False
        print("[model_loader] No trained model found yet — using heuristic fallback. "
              "See docs/MASTER_SETUP_CHECKLIST.md Phase 2 to train one.")


def is_model_loaded() -> bool:
    return _loaded


def _heuristic(features: dict) -> float:
    base = {"Express": 8, "Passenger": 14, "Freight": 25}.get(features.get("train_type"), 15)
    congestion = features.get("congestion_level", 0.3)
    prior = features.get("prior_delay_min", 0)
    return round(base + congestion * 20 + prior * 0.4, 1)


def predict_delay(features: dict) -> float:
    if not _loaded:
        return _heuristic(features)

    row = {}
    for col in CATEGORICAL_COLS:
        le = _encoders[col]
        val = str(features.get(col, ""))
        row[col + "_enc"] = le.transform([val])[0] if val in le.classes_ else 0
    for col in NUMERIC_COLS:
        row[col] = features.get(col, 0)

    import pandas as pd

    X = pd.DataFrame([row])[_feature_cols]
    return round(float(_model.predict(X)[0]), 1)


def get_feature_importance() -> dict:
    if not _loaded:
        return {}
    importance = dict(zip(_feature_cols, _model.feature_importances_.tolist()))
    return dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))


load_model()
