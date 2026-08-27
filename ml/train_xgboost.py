"""Train and evaluate RailSync's synthetic per-section delay model.

Usage from the repository root:
    python ml/train_xgboost.py

The chronological test set is never used during encoder fitting, model-size
selection, or model fitting. Artifacts are saved where the FastAPI backend
expects them, together with evidence that can be shown during a hackathon demo.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
import xgboost
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from xgboost import XGBRegressor


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.delay_features import (  # noqa: E402
    CATEGORICAL_COLUMNS,
    MODEL_FEATURE_COLUMNS,
    NUMERIC_COLUMNS,
    SCHEMA_VERSION,
    TARGET_COLUMN,
)


DEFAULT_DATA_DIR = PROJECT_ROOT / "datasets"
DEFAULT_MODEL_DIR = BACKEND_DIR / "app" / "models"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "docs" / "ML_EVALUATION.md"
RANDOM_SEED = 42

BASE_MODEL_PARAMS = {
    "n_estimators": 600,
    "max_depth": 4,
    "learning_rate": 0.035,
    "subsample": 0.85,
    "colsample_bytree": 0.85,
    "min_child_weight": 3,
    "reg_lambda": 1.0,
    "random_state": RANDOM_SEED,
    "objective": "reg:squarederror",
    "n_jobs": 1,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the RailSync XGBoost delay regressor.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--report-path", type=Path, default=DEFAULT_REPORT_PATH)
    return parser.parse_args()


def load_split(data_dir: Path, split_name: str) -> pd.DataFrame:
    path = data_dir / f"{split_name}_dataset_model_ready.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}. Run datasets/generate_dataset.py first.")

    frame = pd.read_csv(path)
    required_columns = set(CATEGORICAL_COLUMNS + NUMERIC_COLUMNS + [TARGET_COLUMN, "scheduled_departure"])
    missing = sorted(required_columns - set(frame.columns))
    if missing:
        raise ValueError(f"{path.name} is missing required columns: {missing}")
    if frame[sorted(required_columns)].isna().any().any():
        raise ValueError(f"{path.name} contains missing model inputs or target values.")
    if "is_cancelled" in frame.columns and not (frame["is_cancelled"] == 0).all():
        raise ValueError(f"{path.name} must exclude cancelled records.")
    return frame


def assert_chronological_splits(train: pd.DataFrame, validation: pd.DataFrame, test: pd.DataFrame) -> dict:
    boundaries = {}
    for name, frame in (("train", train), ("validation", validation), ("test", test)):
        dates = pd.to_datetime(frame["scheduled_departure"], errors="raise")
        boundaries[name] = {"start": dates.min(), "end": dates.max()}
    if not (boundaries["train"]["end"] < boundaries["validation"]["start"] < boundaries["test"]["start"]):
        raise ValueError("Dataset splits are not strictly chronological and non-overlapping.")
    return {
        split: {key: value.strftime("%Y-%m-%d %H:%M") for key, value in values.items()}
        for split, values in boundaries.items()
    }


def fit_category_mappings(train: pd.DataFrame) -> dict:
    """Fit category mappings on training records only, never validation/test."""

    mappings = {}
    for column in CATEGORICAL_COLUMNS:
        values = sorted(train[column].astype(str).unique().tolist())
        mappings[column] = {value: index for index, value in enumerate(values)}
    return mappings


def make_feature_matrix(frame: pd.DataFrame, mappings: dict, split_name: str) -> pd.DataFrame:
    encoded = pd.DataFrame(index=frame.index)
    for column in NUMERIC_COLUMNS:
        encoded[column] = pd.to_numeric(frame[column], errors="raise").astype(float)

    for column in CATEGORICAL_COLUMNS:
        mapped = frame[column].astype(str).map(mappings[column])
        unknown = sorted(frame.loc[mapped.isna(), column].astype(str).unique().tolist())
        if unknown:
            raise ValueError(
                f"{split_name} contains categories not seen in train for {column}: {unknown}. "
                "Do not silently encode them."
            )
        encoded[f"{column}_enc"] = mapped.astype(int)

    return encoded[MODEL_FEATURE_COLUMNS]


def regression_metrics(actual: pd.Series, predicted: np.ndarray) -> dict:
    return {
        "mae_min": round(float(mean_absolute_error(actual, predicted)), 3),
        "rmse_min": round(float(np.sqrt(mean_squared_error(actual, predicted))), 3),
        "r2": round(float(r2_score(actual, predicted)), 3),
    }


def split_summary(frame: pd.DataFrame, boundaries: dict) -> dict:
    target = frame[TARGET_COLUMN]
    return {
        "rows": int(len(frame)),
        "date_start": boundaries["start"],
        "date_end": boundaries["end"],
        "target_distribution": {
            "mean_min": round(float(target.mean()), 3),
            "median_min": round(float(target.median()), 3),
            "std_min": round(float(target.std()), 3),
            "min_min": round(float(target.min()), 3),
            "max_min": round(float(target.max()), 3),
        },
    }


def write_residual_diagnostics(test: pd.DataFrame, predictions: np.ndarray, model_dir: Path) -> dict:
    output = test[["trip_id", "train_no", "origin_station", "destination_station", "scheduled_departure"]].copy()
    output["actual_delay_min"] = test[TARGET_COLUMN].to_numpy()
    output["predicted_delay_min"] = np.round(predictions, 3)
    output["residual_min"] = np.round(output["predicted_delay_min"] - output["actual_delay_min"], 3)
    output.to_csv(model_dir / "test_predictions.csv", index=False)

    bins = [-np.inf, -12, -8, -5, -2, 0, 2, 5, 8, 12, np.inf]
    labels = [
        "<= -12",
        "-12 to -8",
        "-8 to -5",
        "-5 to -2",
        "-2 to 0",
        "0 to 2",
        "2 to 5",
        "5 to 8",
        "8 to 12",
        "> 12",
    ]
    residual_bins = pd.cut(output["residual_min"], bins=bins, labels=labels, include_lowest=True)
    residual_summary = (
        residual_bins.value_counts(sort=False)
        .rename_axis("residual_bin_min")
        .reset_index(name="records")
    )
    residual_summary["share"] = (residual_summary["records"] / len(output)).round(4)
    residual_summary.to_csv(model_dir / "residual_distribution.csv", index=False)

    residual = output["residual_min"]
    return {
        "test_predictions_path": "backend/app/models/test_predictions.csv",
        "residual_distribution_path": "backend/app/models/residual_distribution.csv",
        "mean_residual_min": round(float(residual.mean()), 3),
        "residual_std_min": round(float(residual.std()), 3),
        "within_5_min_share": round(float((residual.abs() <= 5).mean()), 4),
    }


def markdown_report(metrics: dict) -> str:
    test = metrics["test_metrics"]
    baseline = metrics["test_baseline_metrics"]
    validation = metrics["validation_metrics"]
    splits = metrics["splits"]
    target = splits["train"]["target_distribution"]
    importance_lines = "\n".join(
        f"| {item['feature']} | {item['importance']:.4f} |"
        for item in metrics["feature_importance"]
    )
    return f"""# RailSync ML Evaluation

This evidence was generated by `python ml/train_xgboost.py` on
{metrics['generated_at_utc']}. It describes a **synthetic Tamil Nadu
per-section delay prediction** task, not real-world railway delay accuracy or
conflict prediction.

## Dataset and split

- Dataset: fixed-seed, synthetic records generated by `datasets/generate_dataset.py` from the canonical RailSync network in `backend/app/network.py`.
- Target: `{metrics['target']}` — synthetic arrival delay in minutes for the current section.
- Split: chronological and non-overlapping; train ends before validation, which ends before the untouched test period.
- Train: {splits['train']['rows']:,} rows ({splits['train']['date_start']} to {splits['train']['date_end']})
- Validation: {splits['validation']['rows']:,} rows ({splits['validation']['date_start']} to {splits['validation']['date_end']})
- Test: {splits['test']['rows']:,} rows ({splits['test']['date_start']} to {splits['test']['date_end']})
- Training-target distribution: mean {target['mean_min']:.3f} min, median {target['median_min']:.3f} min, standard deviation {target['std_min']:.3f} min, range {target['min_min']:.3f} to {target['max_min']:.3f} min.

## Features and leakage controls

- Feature count: {metrics['features']['count']}
- Categorical features: {', '.join(metrics['features']['categorical'])}
- Numeric features: {', '.join(metrics['features']['numeric'])}
- Encoding: ordinal mappings fit on **train records only**. Unknown runtime categories cause a safe heuristic fallback instead of arbitrary zero encoding.
- Excluded fields include final actual arrival/departure values, cancellations, and `conflict_flag`.
- `conflict_flag` is an audit-only simulated operational label derived from occupancy/headway and platform pressure before arrival; it is not derived from final delay and is not used by the model.

## Model and evaluation

- Model: XGBoost regression (`XGBRegressor`), selected using validation only and refit on train + validation before one final test evaluation.
- Validation: MAE {validation['mae_min']:.3f} min, RMSE {validation['rmse_min']:.3f} min, R² {validation['r2']:.3f}.
- Final test: **MAE {test['mae_min']:.3f} min**, **RMSE {test['rmse_min']:.3f} min**, **R² {test['r2']:.3f}**.
- Baseline: constant train+validation mean delay. Test MAE {baseline['mae_min']:.3f} min, RMSE {baseline['rmse_min']:.3f} min, R² {baseline['r2']:.3f}.
- Timings: model selection {metrics['timing_seconds']['selection']:.3f}s, final fit {metrics['timing_seconds']['final_fit']:.3f}s, test evaluation {metrics['timing_seconds']['evaluation']:.3f}s.

## Feature importance

| Feature | XGBoost gain proxy |
|---|---:|
{importance_lines}

## Diagnostics and environment

- Test prediction file: `{metrics['diagnostics']['test_predictions_path']}`
- Residual distribution: `{metrics['diagnostics']['residual_distribution_path']}`
- Mean residual: {metrics['diagnostics']['mean_residual_min']:.3f} min; residual standard deviation: {metrics['diagnostics']['residual_std_min']:.3f} min; predictions within ±5 minutes: {metrics['diagnostics']['within_5_min_share']:.1%}.
- Python: {metrics['environment']['python_version']}
- XGBoost: {metrics['environment']['xgboost_version']}
- Execution environment: {metrics['environment']['platform']}

## Honest limitations

- The operational dataset and target are synthetic and reproducible; they are not historical Indian Railways movement data.
- The model predicts delay only. Section/platform conflict detection and rule-based resolution remain simulation logic with a controller in the loop.
- Simulated disruption noise is intentionally unobserved, so predictions retain error rather than recovering a perfectly deterministic formula.
- The official [Indian Railways Train Time Table](https://www.data.gov.in/catalog/indian-railways-train-time-table) is a useful static route/schedule reference, but it is not incorporated as actual delay data and should not be presented as such.
"""


def main() -> None:
    args = parse_args()
    data_dir = args.data_dir.resolve()
    model_dir = args.model_dir.resolve()
    report_path = args.report_path.resolve()
    model_dir.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    train = load_split(data_dir, "train")
    validation = load_split(data_dir, "validation")
    test = load_split(data_dir, "test")
    boundaries = assert_chronological_splits(train, validation, test)

    mappings = fit_category_mappings(train)
    x_train = make_feature_matrix(train, mappings, "train")
    x_validation = make_feature_matrix(validation, mappings, "validation")
    x_test = make_feature_matrix(test, mappings, "test")
    y_train = train[TARGET_COLUMN].astype(float)
    y_validation = validation[TARGET_COLUMN].astype(float)
    y_test = test[TARGET_COLUMN].astype(float)

    selection_started = time.perf_counter()
    candidate = XGBRegressor(**BASE_MODEL_PARAMS, early_stopping_rounds=40)
    candidate.fit(x_train, y_train, eval_set=[(x_validation, y_validation)], verbose=False)
    selection_seconds = time.perf_counter() - selection_started
    best_iteration = getattr(candidate, "best_iteration", None)
    selected_estimators = int(best_iteration) + 1 if best_iteration is not None else BASE_MODEL_PARAMS["n_estimators"]
    selected_estimators = max(1, min(selected_estimators, BASE_MODEL_PARAMS["n_estimators"]))
    validation_predictions = candidate.predict(x_validation)

    x_train_validation = pd.concat([x_train, x_validation], ignore_index=True)
    y_train_validation = pd.concat([y_train, y_validation], ignore_index=True)
    final_params = {**BASE_MODEL_PARAMS, "n_estimators": selected_estimators}
    final_fit_started = time.perf_counter()
    model = XGBRegressor(**final_params)
    model.fit(x_train_validation, y_train_validation, verbose=False)
    final_fit_seconds = time.perf_counter() - final_fit_started

    evaluation_started = time.perf_counter()
    test_predictions = model.predict(x_test)
    test_metrics = regression_metrics(y_test, test_predictions)
    baseline_prediction = np.full(len(y_test), float(y_train_validation.mean()))
    baseline_metrics = regression_metrics(y_test, baseline_prediction)
    evaluation_seconds = time.perf_counter() - evaluation_started

    importance = pd.Series(model.feature_importances_, index=MODEL_FEATURE_COLUMNS).sort_values(ascending=False)
    diagnostics = write_residual_diagnostics(test, test_predictions, model_dir)
    encoder_artifact = {
        "schema_version": SCHEMA_VERSION,
        "categorical_columns": CATEGORICAL_COLUMNS,
        "unknown_value": -1,
        "mappings": mappings,
    }
    metrics = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "model_name": "XGBoost delay regressor",
        "dataset_type": "Synthetic Tamil Nadu per-section operational-delay dataset",
        "target": TARGET_COLUMN,
        # Top-level test metrics preserve the existing frontend contract.
        **test_metrics,
        "validation_metrics": regression_metrics(y_validation, validation_predictions),
        "test_metrics": test_metrics,
        "test_baseline_metrics": baseline_metrics,
        "splits": {
            "train": split_summary(train, boundaries["train"]),
            "validation": split_summary(validation, boundaries["validation"]),
            "test": split_summary(test, boundaries["test"]),
        },
        "features": {
            "count": len(MODEL_FEATURE_COLUMNS),
            "categorical": CATEGORICAL_COLUMNS,
            "numeric": NUMERIC_COLUMNS,
            "model_columns": MODEL_FEATURE_COLUMNS,
            "encoding": "Train-only ordinal mappings; unknown categories use heuristic fallback at runtime.",
        },
        "model_params": final_params,
        "selection": {
            "validation_only": True,
            "selected_n_estimators": selected_estimators,
            "candidate_max_estimators": BASE_MODEL_PARAMS["n_estimators"],
        },
        "feature_importance": [
            {"feature": feature, "importance": round(float(value), 6)}
            for feature, value in importance.items()
        ],
        "diagnostics": diagnostics,
        "timing_seconds": {
            "selection": round(selection_seconds, 3),
            "final_fit": round(final_fit_seconds, 3),
            "evaluation": round(evaluation_seconds, 3),
        },
        "environment": {
            "python_version": sys.version.split()[0],
            "xgboost_version": xgboost.__version__,
            "scikit_learn_version": sklearn.__version__,
            "pandas_version": pd.__version__,
            "platform": platform.platform(),
        },
        "limitations": [
            "Synthetic data; not historical Indian Railways movement data.",
            "Delay prediction only; conflicts remain simulation rules.",
            "No real-world railway safety or signaling claim.",
        ],
    }

    joblib.dump(model, model_dir / "xgb_delay_model.pkl")
    joblib.dump(encoder_artifact, model_dir / "label_encoders.pkl")
    joblib.dump(MODEL_FEATURE_COLUMNS, model_dir / "feature_columns.pkl")
    (model_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    report_path.write_text(markdown_report(metrics), encoding="utf-8")

    print("=== RailSync XGBoost Delay Model ===")
    print(f"Rows: train={len(train):,}, validation={len(validation):,}, test={len(test):,}")
    print(f"Features ({len(MODEL_FEATURE_COLUMNS)}): {', '.join(MODEL_FEATURE_COLUMNS)}")
    print(f"Selected estimators from validation: {selected_estimators}")
    print(
        "Test metrics: "
        f"MAE={test_metrics['mae_min']:.3f} min | "
        f"RMSE={test_metrics['rmse_min']:.3f} min | R2={test_metrics['r2']:.3f}"
    )
    print(
        "Mean baseline: "
        f"MAE={baseline_metrics['mae_min']:.3f} min | "
        f"RMSE={baseline_metrics['rmse_min']:.3f} min | R2={baseline_metrics['r2']:.3f}"
    )
    print(f"Artifacts: {model_dir}")
    print(f"Judge-facing report: {report_path}")


if __name__ == "__main__":
    main()
