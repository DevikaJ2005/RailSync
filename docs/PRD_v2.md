# RailSync Product Requirements Document

## 1. Problem Statement

RailSync is an explainable railway traffic simulation and human-in-the-loop
decision-support system. It helps a human controller observe simulated train
movement, detect simulated conflict situations, review rule-based
recommendations informed by a delay prediction, and apply overrides when
needed.

The goal is to present railway operations in a clear, explainable, demoable
way rather than build a production rail dispatch platform.

## 2. Product Vision

RailSync combines:

- a live simulated rail network
- a delay prediction model
- explainable conflict resolution
- platform occupancy management
- an audit trail for decisions
- a passenger-friendly public view

The XGBoost model predicts simulated delay only. It does not predict conflicts;
section/platform conflict detection and conflict resolution are deterministic
simulation logic.

The system should feel like a control-room dashboard, with the map and
status panels updating live as the simulator advances.

## 3. Users

| Role | Description | View |
|---|---|---|
| Traffic Controller / Admin | Reviews active conflicts, approves or overrides decisions, inspects station and analytics views | Controller View |
| Passenger / Public Viewer | Sees train movement, station platforms, and train search results in read-only form | Passenger View |

## 4. System Concept

RailSync does not track real trains with GPS. Instead, it computes train
positions from:

- fixed station coordinates
- section distances
- train speed
- elapsed simulated time

This makes the map deterministic and lightweight while still showing
realistic movement.

## 5. Core Data Model

### Stations

Stations are defined in `backend/app/network.py` with:

- name
- latitude
- longitude
- platform count

### Sections

Sections define the route graph between stations with:

- section id
- source station
- destination station
- distance in kilometers
- path points for rendering on the map

### Trains

Each train includes:

- train number
- name
- type
- speed
- route
- stations where it stops

## 6. Train State Machine

Every train is always in one state:

| State | Meaning |
|---|---|
| `moving` | Train is moving along a section |
| `checking` | Train is near arrival and is checking the next station |
| `waiting` | Train reached a station but no platform is available |
| `held` | Controller-applied hold is active |
| `at_platform` | Train is boarding/alighting at a platform |
| `completed` | Train has finished its route |

### Important behavior

- Trains near the end of a section enter a check phase before arrival.
- If the next station is not in the stop list, the train passes through.
- If a station has no free platform, the train waits in a queue.
- When a platform is released, the highest-priority waiting train resumes
  automatically.

## 7. Conflict Handling

RailSync focuses on two operational problems:

### Section conflicts

Two or more trains can occupy the same section at the same time in the
simulation. The backend detects this and generates conflict records.

### Platform contention

When a station has no free platform, incoming trains are placed into a
waiting queue. Platform release automatically resumes the highest-priority
waiting train.

## 8. Priority and Resolution

The current resolver ranks trains using a priority score built from:

- train type
- predicted delay
- waiting time
- deterministic tiebreaking by train number

The winner is allowed to proceed, and the other trains are held.

This is intentionally explainable and rule-based rather than opaque.

## 9. Decision Workflow

When the simulator detects a conflict:

1. the backend creates a resolution candidate
2. the candidate is shown in the Controller View
3. the controller can approve or reject it
4. an override can be applied manually for a specific train
5. the decision is written to the log

## 10. Decision Log

The log is an audit trail for:

- conflict detection events
- simulated rule-based recommendations
- controller approvals
- controller overrides
- simulation controls
- what-if simulations

Each entry records the simulated timestamp, trains involved, action taken,
reason, and who triggered the action.

## 11. Pages and Screens

### Controller View

- live network map
- station detail view
- conflict panel
- decision log
- analytics dashboard
- what-if simulator
- simulation controls

### Passenger View

- live network map
- platform board for a selected station
- train search

## 12. Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, Uvicorn, WebSockets, Pydantic |
| ML | XGBoost, scikit-learn, joblib |
| Data | pandas, numpy |
| Database / Log Storage | Firebase Firestore with in-memory fallback |
| Frontend | React 18, Vite |
| Map | React Leaflet, Leaflet, OpenStreetMap tiles |
| Charts | Recharts |
| Optional LLM narration | Groq API, Ollama |

## 13. Non-Functional Goals

- Keep the system responsive while the simulator is running
- Make the reasoning explainable to non-technical viewers
- Keep the UI readable in a control-room style layout
- Support operation even when optional integrations are absent
- Preserve a clean separation between simulation, prediction, and UI

## 14. Out of Scope

- Real-time GPS tracking of actual trains
- Live Indian Railways integration
- Physical signaling or IoT hardware
- Network-wide reinforcement learning control
- Production-grade dispatch optimization

## 15. Success Criteria

The project is successful if:

- the live map updates continuously
- trains transition through the expected states
- waiting trains resume when platforms free up
- conflicts are visible and explainable
- controller actions are recorded in the log
- the passenger view remains readable and useful

## 16. Risks and Constraints

| Risk | Mitigation |
|---|---|
| Simulation feels too synthetic | Use real station names, real coordinates, and realistic route distances |
| Model artifacts are missing | Fall back to heuristic delay prediction |
| Firestore is not configured | Use in-memory logging without breaking the app |
| Narration service is unavailable | Fall back to template reasoning text |
| Browser rendering differs from terminal behavior | Validate the UI in a real browser before final delivery |

## 17. Current Implementation Notes

The codebase currently includes:

- `backend/app/main.py` for API routes and WebSocket streaming
- `backend/app/simulator.py` for the live simulation loop
- `backend/app/network.py` for stations, sections, and trains
- `backend/app/platform_manager.py` for platform queues and resume behavior
- `backend/app/conflict_detection.py` and `backend/app/resolver.py` for conflict handling
- `backend/app/model_loader.py` for delay prediction
- `backend/app/database.py` for log persistence
- `frontend/src/LiveMap.jsx` for the map
- `frontend/src/admin/` for controller widgets
- `frontend/src/user/` for passenger widgets

## 18. Summary

RailSync is best understood as a live rail operations simulator with
human-in-the-loop decision support. It is intentionally small in network
size, but complete enough to demonstrate prediction, resolution, logging,
and a two-audience interface.
