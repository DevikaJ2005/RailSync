# RailSync Data Documentation

## Available data

The repository contains `app/models/test_predictions.csv` with 2,931
chronologically held-out synthetic observations. The raw training table is
not included. It contains these columns:

| Column | Meaning | Runtime use |
| --- | --- | --- |
| `trip_id` | Unique synthetic historical trip | Identifier only |
| `train_no` | Base service identifier such as `T107` | Categorical context |
| `origin_station` | Section origin | Model feature |
| `destination_station` | Section destination | Model feature |
| `scheduled_departure` | Historical scheduled timestamp | Used for historical ordering |
| `actual_delay_min` | Observed delay target in minutes | Target and evaluation feedback |
| `predicted_delay_min` | Saved model prediction | Evaluation only |
| `residual_min` | Prediction minus/relative error stored by the exporter | Evaluation only |

The trained XGBoost artifact uses the feature contract in
`app/delay_features.py`: time-of-day, section distance, remaining stops,
speed, prior delay, section occupancy, nearby train count, platform pressure,
congestion, train type, route endpoints, and day of week.

The target is `delay_min`. Future actual arrival times, future delay, final
platform allocation, conflict outcomes, and controller actions are not model
inputs. The model is trained on synthetic data with chronological train,
validation, and test windows documented in `app/models/metrics.json`.

Because the raw training table is absent, the application does not claim
online learning or real-world railway accuracy. Historical UI context is
calculated from the shipped observed evaluation records and is labelled as
limited context where sample support is low.
