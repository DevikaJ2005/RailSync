"""
RailSync — XGBoost Delay Prediction Model Training

Trains on the synthetic TN dataset and saves the model exactly where
backend/app/model_loader.py expects it.

Usage: python train_xgboost.py
"""

import pandas as pd
import numpy as np
from xgboost import XGBRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import LabelEncoder
import joblib
import os
import json

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "datasets")
MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "backend", "app", "models")
os.makedirs(MODEL_DIR, exist_ok=True)

train_df = pd.read_csv(os.path.join(DATA_DIR, "train_dataset_model_ready.csv"))
test_df = pd.read_csv(os.path.join(DATA_DIR, "test_dataset_model_ready.csv"))
print(f"Train rows: {len(train_df)} | Test rows: {len(test_df)}")

CATEGORICAL_COLS = ["train_type", "origin_station", "destination_station", "day_of_week"]
NUMERIC_COLS = ["num_stops", "speed_kmph", "prior_delay_min", "congestion_level", "hour_of_day"]
TARGET_COL = "delay_min"

encoders = {}
for col in CATEGORICAL_COLS:
    le = LabelEncoder()
    combined = pd.concat([train_df[col], test_df[col]], axis=0).astype(str)
    le.fit(combined)
    train_df[col + "_enc"] = le.transform(train_df[col].astype(str))
    test_df[col + "_enc"] = le.transform(test_df[col].astype(str))
    encoders[col] = le

FEATURE_COLS = NUMERIC_COLS + [c + "_enc" for c in CATEGORICAL_COLS]

X_train, y_train = train_df[FEATURE_COLS], train_df[TARGET_COL]
X_test, y_test = test_df[FEATURE_COLS], test_df[TARGET_COL]

model = XGBRegressor(
    n_estimators=300, max_depth=5, learning_rate=0.05,
    subsample=0.8, colsample_bytree=0.8, random_state=42,
    objective="reg:squarederror",
)
model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

preds = model.predict(X_test)
metrics = {
    "mae_min": round(float(mean_absolute_error(y_test, preds)), 2),
    "rmse_min": round(float(np.sqrt(mean_squared_error(y_test, preds))), 2),
    "r2": round(float(r2_score(y_test, preds)), 3),
    "train_rows": len(train_df),
    "test_rows": len(test_df),
}
print("\n=== Model Evaluation ===")
print(f"MAE:  {metrics['mae_min']:.2f} min")
print(f"RMSE: {metrics['rmse_min']:.2f} min")
print(f"R^2:  {metrics['r2']:.3f}")

importance = pd.Series(model.feature_importances_, index=FEATURE_COLS).sort_values(ascending=False)
print("\n=== Feature Importance ===")
print(importance)

joblib.dump(model, os.path.join(MODEL_DIR, "xgb_delay_model.pkl"))
joblib.dump(encoders, os.path.join(MODEL_DIR, "label_encoders.pkl"))
joblib.dump(FEATURE_COLS, os.path.join(MODEL_DIR, "feature_columns.pkl"))
with open(os.path.join(MODEL_DIR, "metrics.json"), "w", encoding="utf-8") as metrics_file:
    json.dump(metrics, metrics_file, indent=2)
print(f"\nModel saved to {MODEL_DIR}")
