"""Load RailSync's XGBoost delay model with a safe runtime fallback.

The model is intentionally limited to synthetic per-section delay prediction.
Operational conflict detection and resolution remain in the simulator.
"""

from __future__ import annotations

import math
import os
from pathlib import Path

from dotenv import load_dotenv

from app.delay_features import CATEGORICAL_COLUMNS, MODEL_FEATURE_COLUMNS, NUMERIC_COLUMNS, SCHEMA_VERSION


load_dotenv(Path(__file__).resolve().parents[1] / ".env")

MODEL_DIR = Path(__file__).resolve().parent / "models"
MODEL_PATH = MODEL_DIR / "xgb_delay_model.pkl"
ENCODERS_PATH = MODEL_DIR / "label_encoders.pkl"
FEATURES_PATH = MODEL_DIR / "feature_columns.pkl"
METRICS_PATH = MODEL_DIR / "metrics.json"

_model = None
_encoder_artifact = None
_feature_cols = None
_loaded = False
_metrics: dict = {}
_fallback_warnings: set[str] = set()
_fallback_reason = "XGBoost model unavailable"


def load_model() -> None:
    """Load compatible artifacts, otherwise leave the simulator usable."""

    global _model, _encoder_artifact, _feature_cols, _loaded, _metrics, _fallback_reason
    _model = None
    _encoder_artifact = None
    _feature_cols = None
    _metrics = {}
    _loaded = False
    _fallback_reason = "XGBoost model unavailable"

    model_enabled = os.getenv("DELAY_MODEL_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
    if not model_enabled:
        _fallback_reason = "XGBoost disabled by DELAY_MODEL_ENABLED"
        print("[model_loader] Delay model disabled by DELAY_MODEL_ENABLED; using heuristic fallback.")
        return

    required = (MODEL_PATH, ENCODERS_PATH, FEATURES_PATH)
    if not all(path.exists() for path in required):
        _fallback_reason = "XGBoost model artifacts are incomplete"
        print("[model_loader] No trained model artifacts found; using heuristic fallback.")
        return

    try:
        import joblib

        model = joblib.load(MODEL_PATH)
        encoder_artifact = joblib.load(ENCODERS_PATH)
        feature_cols = joblib.load(FEATURES_PATH)

        if list(feature_cols) != MODEL_FEATURE_COLUMNS:
            raise ValueError(
                "Feature artifact does not match the current delay schema. "
                "Regenerate the dataset and retrain the model."
            )
        if not isinstance(encoder_artifact, dict) or "mappings" not in encoder_artifact:
            raise ValueError("Encoder artifact is from an unsupported schema. Retrain the model.")
        if encoder_artifact.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("Encoder schema version differs from runtime schema. Retrain the model.")

        mappings = encoder_artifact["mappings"]
        for column in CATEGORICAL_COLUMNS:
            if not isinstance(mappings.get(column), dict) or not mappings[column]:
                raise ValueError(f"Encoder mapping missing for {column}.")

        if METRICS_PATH.exists():
            import json

            _metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
        _model = model
        _encoder_artifact = encoder_artifact
        _feature_cols = list(feature_cols)
        _loaded = True
        _fallback_reason = ""
        print("[model_loader] Trained XGBoost delay model loaded.")
    except Exception as error:
        _fallback_reason = f"XGBoost artifact validation failed: {error}"
        print(f"[model_loader] Model artifact validation failed ({error}); using heuristic fallback.")


def is_model_loaded() -> bool:
    return _loaded


def _heuristic(features: dict) -> float:
    """A transparent fallback when model artifacts/configuration are unavailable."""

    base = {"Express": 5.0, "Passenger": 8.0, "Freight": 12.0}.get(features.get("train_type"), 9.0)
    congestion = float(features.get("congestion_level", 0.30) or 0.30)
    prior_delay = float(features.get("prior_delay_min", 0.0) or 0.0)
    section_occupancy = float(features.get("section_occupancy", 0.0) or 0.0)
    platform_ratio = float(features.get("destination_platform_occupancy_ratio", 0.0) or 0.0)
    no_free_platform = 2.5 if float(features.get("destination_platform_available_count", 1) or 0) <= 0 else 0.0
    return round(max(0.0, base + congestion * 8.0 + prior_delay * 0.53 + section_occupancy + platform_ratio * 4.0 + no_free_platform), 1)


def _prepare_model_row(features: dict) -> dict:
    if _encoder_artifact is None:
        raise ValueError("No encoder artifact is loaded.")

    row = {}
    mappings = _encoder_artifact["mappings"]
    for column in CATEGORICAL_COLUMNS:
        if column not in features:
            raise ValueError(f"Missing runtime category: {column}")
        value = str(features[column])
        if value not in mappings[column]:
            raise ValueError(f"Unknown runtime category for {column}: {value!r}")
        row[f"{column}_enc"] = mappings[column][value]

    for column in NUMERIC_COLUMNS:
        if column not in features:
            raise ValueError(f"Missing runtime numeric feature: {column}")
        value = float(features[column])
        if not math.isfinite(value):
            raise ValueError(f"Invalid runtime numeric feature: {column}")
        row[column] = value
    return row


def _warn_and_fallback(message: str, features: dict) -> float:
    global _fallback_reason
    _fallback_reason = f"XGBoost inference failed: {message}"
    if message not in _fallback_warnings:
        print(f"[model_loader] {message}; using heuristic fallback.")
        _fallback_warnings.add(message)
    return _heuristic(features)


def predict_delay(features: dict) -> float:
    """Return a model prediction, falling back safely on schema problems."""

    if not _loaded:
        return _heuristic(features)
    try:
        import pandas as pd

        row = _prepare_model_row(features)
        matrix = pd.DataFrame([row])[_feature_cols]
        return round(float(_model.predict(matrix)[0]), 1)
    except Exception as error:
        return _warn_and_fallback(str(error), features)


def get_feature_importance() -> dict:
    if not _loaded:
        return {}
    values = dict(zip(_feature_cols, _model.feature_importances_.tolist()))
    return dict(sorted(values.items(), key=lambda item: item[1], reverse=True))


def get_model_metrics() -> dict:
    return _metrics


def get_model_scope() -> dict:
    return {
        "prediction": "Synthetic per-section train delay prediction",
        "conflicts": "Simulated section/platform conflicts are detected and resolved by deterministic operational rules.",
        "forecast_timing": "Current section delay prediction is carried forward as a single forecast offset for future movement projection.",
        "schema_version": SCHEMA_VERSION,
        "training_status": "Trained artifact loaded from the repository; automatic online retraining is not implemented.",
    }


def get_model_status() -> dict:
    """Return an honest runtime status without exposing artifact paths."""

    if _loaded:
        return {
            "model": "XGBoost",
            "status": "active",
            "training_data": "synthetic",
            "fallback": False,
            "reason": None,
            "online_learning": "disabled",
            "runtime_feedback": "unavailable",
        }
    return {
        "model": "Heuristic",
        "status": "fallback",
        "training_data": "synthetic",
        "fallback": True,
        "reason": _fallback_reason,
        "online_learning": "disabled",
        "runtime_feedback": "unavailable",
    }


load_model()
