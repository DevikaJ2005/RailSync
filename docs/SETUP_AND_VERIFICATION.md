# RailSync Setup and Verification

RailSync is a simulated Tamil Nadu railway decision-support demo. The model
predicts synthetic section delay; simulated section/platform conflicts are
detected and resolved through deterministic, explainable rules.

## Prerequisites

- Python 3.11+
- Node.js 18+
- Optional: Firebase credentials for persistent logs, Groq or Ollama for
  narration. The app works without optional services.

## Start the backend

```powershell
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

The backend reads `backend/.env` by absolute project path. Keep that file and
`firebase-key.json` private. Confirm the generated model is enabled and then
visit `http://127.0.0.1:8000/`:

```json
{
  "status": "ok",
  "model_loaded": true,
  "scope": {
    "prediction": "Synthetic per-section train delay prediction"
  }
}
```

If model artifacts are intentionally absent or `DELAY_MODEL_ENABLED=false`,
the backend stays usable with the documented heuristic fallback.

## Start the frontend

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

Open `http://127.0.0.1:5173`. The frontend defaults to the backend at port
8000; configure `VITE_API_URL` and `VITE_WS_URL` only for a different target.

## Regenerate the deterministic data and model

Run these commands from the repository root:

```powershell
python datasets/generate_dataset.py
python ml/train_xgboost.py
```

The generator has a fixed seed and writes train/validation/test full and
model-ready CSVs using the canonical network in `backend/app/network.py`.
The model script creates the backend artifacts plus
`docs/ML_EVALUATION.md`; do not select/tune on the test period.

## Backend verification

1. `GET /api/network` returns 8 stations, 8 sections, and the base services.
2. `GET /api/model-info` returns `model_loaded: true`, 14 feature columns,
   holdout metrics, feature importance, and an explicit scope statement.
3. `GET /api/state` returns `sim_time`, trains, platform occupancy, conflicts,
   and rule-based recommendations.
4. Request `/api/state` twice after one tick interval; `sim_time` must advance
   even if no WebSocket client is connected.
5. Connect to `/ws/live`; each message must contain train
   `predicted_delay_min`, `conflicts`, and `resolutions` fields.
6. Use `POST /api/whatif` and confirm projected conflict/recommendation output.
7. Approve/reject an active recommendation in the Controller View, then verify
   a decision-log entry and controller hold behavior.
8. Apply and release a manual simulated hold from the Controller View where an
   active moving train is eligible; verify it appears in `controller_holds`.
9. Pause, confirm `sim_time` stays fixed, resume, and confirm it advances.
10. Reset after testing to restore the reproducible demo timetable.

## Frontend verification

1. The Controller View connects and shows the simulation clock, not a local
   wall clock.
2. Map markers move and display **Predicted delay (model)**.
3. The conflict panel states that conflicts/recommendations are simulated
   operational logic, while delay is the model output.
4. Analytics reports evaluation metrics and operational counters separately;
   it must not make an unmeasured “with AI vs without AI” claim.
5. Station and Passenger views show current platform allocation, waiting
   queues, and train status.
6. The production build succeeds with `npm.cmd run build`.

## Validation evidence from the final run

The included artifacts were generated from a chronological, untouched
synthetic test period:

| Measure | Result |
|---|---:|
| Train / validation / test rows | 11,739 / 2,919 / 2,931 |
| Test MAE | 3.001 min |
| Test RMSE | 3.872 min |
| Test R² | 0.807 |
| Mean baseline test MAE | 7.233 min |

Use [ML_EVALUATION.md](ML_EVALUATION.md) as the judge-facing source for
generated feature importance, diagnostics, timings, environment metadata,
and limitations.
