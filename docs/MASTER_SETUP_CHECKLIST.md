# RailSync Master Setup Checklist

This checklist is the practical setup path for the current repository
state. Use it to get the app running locally, then decide whether you want
to enable optional integrations.

## 1. What Is Already In The Repo

The repository already includes:

- backend source code
- frontend source code
- synthetic dataset CSVs
- trained model artifacts in `backend/app/models/`
- documentation for setup and the product scope

That means the app should run locally without retraining the model first.

## 2. Required Accounts

You do not need cloud accounts for basic local use.

Optional accounts if you want the extra integrations:

- Firebase for persistent decision logs
- Groq for hosted narration
- Ollama if you want local narration
- Railway for backend deployment
- Vercel for frontend deployment

## 3. Local Startup Checklist

### Backend

- [ ] Install Python dependencies with `pip install -r requirements.txt`
- [ ] Create `backend/.env` if you want optional integrations
- [ ] Start the backend with `uvicorn app.main:app --reload --port 8000`
- [ ] Open `http://localhost:8000/`
- [ ] Confirm `model_loaded` is reported

### Frontend

- [ ] Install frontend dependencies with `npm install`
- [ ] Start the frontend with `npm run dev`
- [ ] Open `http://localhost:5173`
- [ ] Confirm the map loads and the live state is updating

## 4. Optional Environment Variables

### Backend

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
- `OLLAMA_TIMEOUT_SECONDS`

### Frontend

- `VITE_API_URL`
- `VITE_WS_URL`

## 5. Optional Feature Setup

### Firebase decision log

- [ ] Create a Firebase project
- [ ] Enable Firestore
- [ ] Create a service account key
- [ ] Set `FIREBASE_CREDENTIALS_PATH` locally or `FIREBASE_CREDENTIALS_JSON` in deployment
- [ ] Set `FIREBASE_ENABLED=true` if you want the app to use Firestore

### Groq narration

- [ ] Create a Groq account
- [ ] Generate an API key
- [ ] Set `GROQ_API_KEY`
- [ ] Optionally set `GROQ_MODEL`

### Ollama narration

- [ ] Install Ollama
- [ ] Pull a model such as `gemma3:4b`
- [ ] Set `LLM_PROVIDER=ollama`
- [ ] Optionally set `OLLAMA_MODEL` and `OLLAMA_URL`

## 6. Model Retraining Checklist

Retraining is optional because model artifacts are already present.

If you want to retrain:

- [ ] Run `python ml/train_xgboost.py`
- [ ] Confirm the script completes successfully
- [ ] Confirm the `.pkl` files are updated in `backend/app/models/`
- [ ] Restart the backend

## 7. Dataset Checklist

- [ ] Review `datasets/generate_dataset.py`
- [ ] Inspect `train_dataset_model_ready.csv`
- [ ] Inspect `test_dataset_model_ready.csv`
- [ ] Confirm the column set matches the training script

## 8. Verification Checklist

### Backend

- [ ] `GET /` returns a healthy status
- [ ] `GET /api/network` returns stations, sections, and trains
- [ ] `GET /api/state` returns live simulator state
- [ ] `GET /api/analytics` returns counters and delay totals
- [ ] `GET /api/model-info` returns model metadata
- [ ] `GET /api/logs` returns log entries

### Frontend

- [ ] Controller View loads
- [ ] Passenger View loads
- [ ] The live map renders stations and routes
- [ ] Train markers move over time
- [ ] Station detail and platform views respond to clicks
- [ ] The conflict, log, analytics, and what-if panels open

## 9. Deployment Checklist

### Backend on Railway

- [ ] Set the start command to `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- [ ] Set CORS to your frontend URL
- [ ] Add Firebase and Groq environment variables if needed

### Frontend on Vercel

- [ ] Set the framework preset to Vite
- [ ] Set `VITE_API_URL` to the backend URL
- [ ] Set `VITE_WS_URL` to the backend WebSocket URL

## 10. File Checklist

- [ ] `backend/app/main.py`
- [ ] `backend/app/simulator.py`
- [ ] `backend/app/network.py`
- [ ] `backend/app/platform_manager.py`
- [ ] `backend/app/conflict_detection.py`
- [ ] `backend/app/resolver.py`
- [ ] `backend/app/model_loader.py`
- [ ] `backend/app/database.py`
- [ ] `frontend/src/App.jsx`
- [ ] `frontend/src/LiveMap.jsx`
- [ ] `frontend/src/admin/AdminPanel.jsx`
- [ ] `frontend/src/user/UserPanel.jsx`
- [ ] `ml/train_xgboost.py`

## 11. Clean Repo Checklist

- [ ] Do not commit `backend/.env`
- [ ] Do not commit Firebase private keys
- [ ] Do not commit generated deployment secrets
- [ ] Keep model artifacts only if you want the app to run immediately

## 12. Final Sanity Check

Before calling the project done:

- [ ] The backend starts without errors
- [ ] The frontend starts without errors
- [ ] The live socket updates
- [ ] The map and panels are visible
- [ ] At least one optional integration is configured, if you need it

## 13. Recommended Next Steps

1. Add screenshots to the README.
2. Capture a short demo video.
3. Configure Firebase if you want persistent logs.
4. Configure Groq or Ollama if you want narrated decisions.
