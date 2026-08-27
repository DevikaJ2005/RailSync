# RailSync Final Hackathon Checklist

## Scope check

- [ ] Describe RailSync as an **explainable railway traffic simulation and
  human-in-the-loop decision-support system**.
- [ ] Say the model predicts **synthetic per-section delay**.
- [ ] Say section/platform conflicts and recommendations come from simulated,
  deterministic operational logic.
- [ ] Do not claim real-world railway conflict prediction, signaling, GPS
  tracking, safety certification, or production dispatch autonomy.

## Clean setup

- [ ] Keep `backend/.env` and `backend/firebase-key.json` private.
- [ ] Install backend dependencies: `pip install -r backend/requirements.txt`.
- [ ] Install frontend dependencies: `npm.cmd install` from `frontend/`.
- [ ] Start the backend: `python -m uvicorn app.main:app --reload --port 8000`
  from `backend/`.
- [ ] Start the frontend: `npm.cmd run dev` from `frontend/`.
- [ ] Confirm `GET /` reports `model_loaded: true` when bundled artifacts and
  `DELAY_MODEL_ENABLED=true` are present.

## Dataset and model reproducibility

- [ ] Run `python datasets/generate_dataset.py` from the project root.
- [ ] Confirm train/validation/test full CSVs each exist.
- [ ] Confirm corresponding model-ready CSVs exclude cancelled records.
- [ ] Verify split dates are chronological: Jan–Apr train, May validation,
  late-May–Jun test.
- [ ] Verify every generated route section exists in `backend/app/network.py`.
- [ ] Verify the target is `delay_min` and `conflict_flag` is not a model input.
- [ ] Run `python ml/train_xgboost.py`.
- [ ] Confirm the five model/evidence artifacts and `docs/ML_EVALUATION.md` are
  updated.
- [ ] Use the generated report, not memory or a manually edited number, when
  presenting MAE, RMSE, R², baseline, importance, or timing.

## Live demonstration flow

1. [ ] Show the model-loaded scope statement and the Controller View.
2. [ ] Explain that the map clock is simulated time and train positions are
   computed, not GPS.
3. [ ] Point out **Predicted delay (model)** for a moving train.
4. [ ] Show a simulated section/platform conflict.
5. [ ] Explain the rule-based score: train type, predicted delay, wait time,
   and deterministic tiebreaker.
6. [ ] Approve or reject the recommendation; show the controller hold/release.
7. [ ] Demonstrate an eligible manual hold/release or platform override.
8. [ ] Open the decision log and show the associated record.
9. [ ] Run a non-persistent what-if delay scenario.
10. [ ] Switch to Passenger View and show station/platform information.

## Final validation

- [ ] `GET /api/network`, `/api/state`, `/api/analytics`, `/api/model-info`,
  and `/api/logs` return valid payloads.
- [ ] `/ws/live` advances shared state with one or many browser clients.
- [ ] Pause/resume/reset/speed controls work.
- [ ] What-if, controller decision, and manual override calls work.
- [ ] The frontend production build passes: `npm.cmd run build`.
- [ ] Optional narration failing does not block the simulation or controller
  actions; the deterministic explanation remains visible.
- [ ] The judge-facing wording matches the scope check above.
