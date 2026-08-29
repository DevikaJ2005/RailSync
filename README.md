# RailSync

RailSync is an **explainable railway traffic simulation and
human-in-the-loop decision-support system** built around a small Tamil Nadu
network. It predicts a simulated train's section delay and detects/resolves
simulated section and platform conflicts through transparent operational
rules.

It is a hackathon prototype, not a production dispatch, signaling, GPS, or
railway-safety system.

## What RailSync does

- Simulates train movement across eight Tamil Nadu stations and eight route
  sections using fixed distances, train speeds, platform counts, and a virtual
  clock.
- Uses an XGBoost regression model to predict **synthetic per-section delay**
  in minutes from pre-event operational features.
- Detects simulated section occupancy conflicts and platform contention with
  deterministic logic.
- Produces explainable, rule-based recommendations that consider train class,
  model-predicted delay, and waiting time.
- Keeps the controller in control: recommendations can be approved, rejected,
  manually held/released, or overridden where the simulated state permits it.
- Streams the shared simulation state to a controller dashboard and a
  passenger-facing read-only view.

## Scope and honest claims

| Component | What it does | What it does not claim |
|---|---|---|
| XGBoost model | Predicts synthetic section delay in minutes | Real-world Indian Railways delay accuracy or conflict prediction |
| Conflict detection | Finds concurrent simulated section occupancy | Railway signaling, collision prevention, or safety certification |
| Resolver | Applies explainable priority rules to simulated conflicts | An ML conflict classifier or autonomous train control |
| Map | Renders simulated movement over real approximate station geography | GPS tracking of real trains |

## Architecture

```text
Synthetic dataset generator ──> chronological CSV splits ──> XGBoost training
       ^                                                                  │
       │                                                                  v
canonical TN network <── shared feature schema <── FastAPI simulator <── model artifacts
                                                │
                                                ├── REST API
                                                └── WebSocket shared state ──> React controller/passenger views
```

### Backend

- `backend/app/network.py` is the canonical source for stations, sections,
  distances, platform counts, and base train routes.
- `backend/app/simulator.py` advances the shared virtual clock independently
  of WebSocket client count; it builds pre-movement delay features from current
  occupancy and platform state.
- `backend/app/conflict_detection.py` and `resolver.py` implement simulated,
  rule-based conflict handling.
- `backend/app/model_loader.py` validates the model schema and uses a transparent
  heuristic fallback if artifacts are unavailable or a runtime category is
  unknown.
- `backend/app/main.py` exposes REST endpoints and a live WebSocket feed.

### Frontend

React + Vite consumes `/api/network`, `/api/model-info`, analytics/log APIs,
and `ws/live`. The controller view differentiates the model delay output from
the operational conflict rules and shows the simulation clock rather than a
misleading local wall clock.

## Dataset and model

The bundled dataset is reproducible, synthetic, and intentionally aligned with
the backend network. It represents a train at the start of a section. All
delay-model features are known before the train reaches its destination:

- Categorical: `train_type`, `origin_station`, `destination_station`,
  `day_of_week`
- Numeric: `hour_of_day`, `section_distance_km`, `remaining_stops`,
  `speed_kmph`, `prior_delay_min`, `section_occupancy`,
  `nearby_train_count`, `destination_platform_occupancy_ratio`,
  `destination_platform_available_count`, `congestion_level`
- Target: `delay_min`

`conflict_flag` is retained only as an audit field. It is generated from
simulated occupancy/headway and platform pressure, not final delay, and is
never passed to the model.

The data uses fixed-seed chronological splits:

| Split | Full rows | Model-ready rows | Period |
|---|---:|---:|---|
| Train | 12,000 | 11,739 | 2026-01-01 to 2026-04-30 |
| Validation | 3,000 | 2,919 | 2026-05-01 to 2026-05-30 |
| Test | 3,000 | 2,931 | 2026-05-31 to 2026-06-29 |

The final XGBoost model uses 14 encoded features. On its untouched
chronological synthetic test period it achieved:

| Metric | XGBoost | Mean-delay baseline |
|---|---:|---:|
| MAE | **3.001 min** | 7.233 min |
| RMSE | **3.872 min** | 8.816 min |
| R² | **0.807** | -0.000 |

See [the generated ML evaluation](docs/ML_EVALUATION.md) for actual run
metadata, validation metrics, feature importance, residual diagnostics,
environment versions, and limitations.

## Repository layout

```text
backend/
  app/
    delay_features.py       Shared data/model/runtime feature contract
    simulator.py            Live simulation and operational feature snapshot
    conflict_detection.py   Deterministic simulated conflict detection
    resolver.py             Explainable rule-based recommendation logic
    models/                 Trained XGBoost model and evaluation artifacts
datasets/
  generate_dataset.py       Fixed-seed, project-relative synthetic generator
  *_dataset_{full,model_ready}.csv
ml/
  train_xgboost.py          Chronological train/validation/test evaluation
docs/
  ML_EVALUATION.md          Judge-facing evidence generated by training
frontend/
  src/                      React controller and passenger views
```

## Run locally

### Backend

```powershell
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --reload --port 8000
```

`--host 0.0.0.0` binds all interfaces so phones on the same Wi-Fi can reach
the API; `127.0.0.1` (the default) is loopback-only and blocks Expo Go.

`backend/.env` contains optional Firebase and narration settings. Do not commit
it or Firebase credentials. With the bundled artifacts and
`DELAY_MODEL_ENABLED=true`, `GET /` reports `model_loaded: true`.

### Frontend

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

Open `http://127.0.0.1:5173`. Configure `VITE_API_URL` and `VITE_WS_URL` if
the backend is elsewhere.

### Mobile (Expo Go)

```powershell
cd mobile
npm.cmd install
npx expo start
```

Scan the QR code with the Expo Go app. The mobile client auto-detects the
backend at the Expo development host on port 8000; the address can be
overridden on the sign-in screen (tap the backend line under the password
field, then use "Test connection"). Requirements for sign-in to work from a
phone:

- The backend must run with `--host 0.0.0.0`.
- The phone and computer must share the same Wi-Fi network. Networks with
  client isolation (common on campus/office Wi-Fi) block device-to-device
  traffic — use `npx expo start --tunnel` and set the backend address
  manually in that case.

### Sign-in

The app requires a role-based sign-in (single port — the view is chosen by the
signed-in role, not by a separate port). The same sample accounts are shown and
auto-fill on the login card:

| Role | Username | Password |
|---|---|---|
| Controller (full control room) | `controller` | `admin@123` |
| Passenger (read-only live view) | `passenger` | `pass@123` |

- `controller` unlocks the full control-room dashboard: station detail,
  conflict recommendations with approve/reject, hold/release overrides,
  what-if delay simulation, analytics, and the decision log.
- `passenger` gets the read-only passenger experience: live map, platform
  board, and train search.

Tokens are short-lived HMAC-signed sessions issued by `POST /api/auth/login`.
Controller-only endpoints return `401` without a token and `403` for the
passenger role. The backend reads `RAILSYNC_AUTH_SECRET` and
`RAILSYNC_TOKEN_TTL_SECONDS` from `backend/.env` if you want to override the
development defaults.

## Regenerate data and model evidence

From the repository root:

```powershell
python datasets/generate_dataset.py
python ml/train_xgboost.py
```

The generator has a fixed seed and writes project-relative CSVs, including the
validation split. Training fits ordinal category mappings on the train split
only, selects the number of estimators on validation, refits on train plus
validation, and evaluates test once. It writes:

- `backend/app/models/xgb_delay_model.pkl`
- `backend/app/models/label_encoders.pkl`
- `backend/app/models/feature_columns.pkl`
- `backend/app/models/metrics.json`
- `backend/app/models/test_predictions.csv`
- `backend/app/models/residual_distribution.csv`
- `docs/ML_EVALUATION.md`

## API summary

- `POST /api/auth/login` — sign in with a username/password, returns a token and role
- `GET /api/auth/me` — validate the current token and return its role
- `GET /` — health, model status, and scope statement
- `GET /api/network` — canonical simulated network
- `GET /api/state` — shared current simulation state
- `GET /api/model-info` — model metrics, feature importance, and scope
- `ws://127.0.0.1:8000/ws/live` — live shared state

Endpoints marked *(controller)* require a controller-role bearer token:

- `GET /api/analytics` *(controller)* — simulated operational counters
- `GET /api/logs` *(controller)* — controller/simulation decision log
- `POST /api/whatif` *(controller)* — non-persistent delay scenario
- `POST /api/decisions/approve` *(controller)* — approve/reject a rule-based recommendation
- `POST /api/override` *(controller)* — simulated controller hold/release or eligible
  platform-allocation override
- `POST /api/simulation/{pause,resume,reset,speed}` *(controller)* — simulation controls

## Data grounding and limitations

The station names, approximate geography, section distances, and simulated
network are local project data. The official [Indian Railways Train Time
Table](https://www.data.gov.in/catalog/indian-railways-train-time-table) can
be used as a schedule/route reference in a future data-grounding pass; it is a
static timetable and must not be represented as historical or live delay data.

The bundled operational records remain synthetic because verified historical
movement and platform-occupancy data is not included. RailSync therefore must
be described as a simulated decision-support demonstration, with model results
limited to its synthetic held-out test set.
