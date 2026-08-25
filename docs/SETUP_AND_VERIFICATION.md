# RailSync Setup and Verification

This document explains how the current RailSync codebase is structured,
how to run it locally, and what to check after startup.

## What The Project Contains

RailSync has four main parts:

- `backend/` - FastAPI app, simulator, conflict logic, logging, and model loading
- `frontend/` - React + Vite UI for controller and passenger views
- `datasets/` - synthetic data generation and CSV outputs
- `ml/` - XGBoost training script for the delay model

The backend exposes a live simulation over HTTP and WebSocket. The frontend
renders a map, station boards, conflict panels, analytics, and what-if
tools.

## Core Runtime Behavior

The current implementation includes:

- a train state machine with `moving`, `checking`, `waiting`, `held`,
  `at_platform`, and `completed`
- real station coordinates and section paths for the map
- platform occupancy tracking and waiting queues
- section conflict detection
- priority-based conflict resolution
- optional controller approval or manual override
- a decision log backed by Firestore with in-memory fallback
- optional LLM narration through Groq or Ollama
- XGBoost-based delay prediction with heuristic fallback

## Local Setup

### 1. Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

The backend reads environment variables from `backend/.env` if present.
There is no required `.env.example` file in this repository, so create the
file manually if you want to configure optional services.

Useful optional variables:

- `CORS_ALLOWED_ORIGINS`
- `SIMULATION_TICK_SECONDS`
- `DELAY_MODEL_ENABLED`
- `FIREBASE_ENABLED`
- `FIREBASE_CREDENTIALS_JSON`
- `FIREBASE_CREDENTIALS_PATH`
- `GROQ_API_KEY`
- `GROQ_MODEL`
- `LLM_PROVIDER`
- `OLLAMA_URL`
- `OLLAMA_MODEL`

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend defaults to:

- `http://127.0.0.1:8000` for REST
- `ws://127.0.0.1:8000` for WebSocket

If you want to point it elsewhere, set:

- `VITE_API_URL`
- `VITE_WS_URL`

### 3. Open the app

- Frontend: `http://localhost:5173`
- Backend health check: `http://localhost:8000`

## What To Verify After Startup

### Backend checks

1. Visit `http://localhost:8000/`
2. Confirm the response shows:
   - `status: ok`
   - `service: RailSync backend`
   - `model_loaded` either `true` or `false`

3. Visit `http://localhost:8000/api/network`
4. Confirm the payload includes:
   - stations
   - sections
   - trains

5. Visit `http://localhost:8000/api/state`
6. Confirm the payload includes:
   - `sim_time`
   - `paused`
   - `speed_multiplier`
   - `trains`
   - `platforms`
   - `next_departure_time`

7. Visit `http://localhost:8000/api/analytics`
8. Confirm the payload includes:
   - conflicts detected
   - conflicts resolved
   - deadlocks broken
   - forced releases
   - delay totals

### Frontend checks

1. Open `http://localhost:5173`
2. Confirm the map loads
3. Confirm you can switch between:
   - Controller View
   - Passenger View
4. Confirm the live simulation updates in place
5. Confirm station clicks open the station detail or platform view

### WebSocket checks

The frontend listens to:

- `ws://127.0.0.1:8000/ws/live`

If the socket is connected, the live state should update automatically.

### Optional feature checks

#### Delay model

The repo includes trained model artifacts in:

- `backend/app/models/xgb_delay_model.pkl`
- `backend/app/models/label_encoders.pkl`
- `backend/app/models/feature_columns.pkl`

If those files exist, `model_loaded` should be `true`. If they are
missing, the backend falls back to the heuristic predictor.

#### Decision log

If Firebase is configured, decision log entries are written to Firestore.
If not, the app uses in-memory logging and still works.

#### Narration

If Groq or Ollama is configured, decision reasoning can be narrated in
simple English. If neither is configured, the original reason text is used.

## Training The Model

The model can be retrained from the CSVs in `datasets/`:

```bash
cd ml
python train_xgboost.py
```

This script:

- loads `train_dataset_model_ready.csv` and `test_dataset_model_ready.csv`
- encodes categorical features
- trains an `XGBRegressor`
- prints evaluation metrics
- rewrites the `.pkl` files in `backend/app/models/`
- writes holdout metrics to `backend/app/models/metrics.json`

The current saved model reports the following on the held-out test set:

- MAE: **7.72 minutes**
- RMSE: **10.38 minutes**
- R²: **0.450**
- Training/test rows: **7,800 / 1,948**

The same metrics are available from `GET /api/model-info` and in the
Controller View's Analytics tab.

## Deployment Notes

The current codebase is structured for separate backend and frontend
deployment.

### Backend

- run with Uvicorn
- set CORS to allow the frontend origin
- supply Firebase credentials if you want persistent logs
- supply Groq credentials if you want hosted narration

### Frontend

- build with Vite
- point `VITE_API_URL` and `VITE_WS_URL` at the deployed backend

## Honest Limitations

- The network is intentionally small
- Positions are calculated, not GPS-tracked
- Conflict resolution is rule-based and explainable, not reinforcement-learning based
- Firebase and LLM narration are optional, not mandatory
- Visual review still matters; a browser run is the real final check

## Quick Reference

- Backend entry point: `backend/app/main.py`
- Simulator: `backend/app/simulator.py`
- Network definition: `backend/app/network.py`
- Conflict resolution: `backend/app/resolver.py`
- Delay model loading: `backend/app/model_loader.py`
- Decision logs: `backend/app/database.py`
- Frontend app shell: `frontend/src/App.jsx`
- Live map: `frontend/src/LiveMap.jsx`
