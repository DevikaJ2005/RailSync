import os
import sys
import unittest
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("DELAY_MODEL_ENABLED", "false")
os.environ.setdefault("FIREBASE_ENABLED", "false")

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.conflict_detection import _direction_relation, detect_all_conflicts, detect_section_conflicts
from app.database import get_logs, log_decision
from app.future_timing import project_section_windows
from app.network import get_distance
from app.resolver import resolve_conflicts
from app.simulator import Simulator
from app.models import TrainState, TrainStatus
from app.model_loader import FEATURES_PATH, get_model_status, load_model, MODEL_FEATURE_COLUMNS
from app import llm_narration
from app.llm_narration import narrate_decision


class RailSyncConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.sim = Simulator()
        # Make the test state small and deterministic.
        self.sim.trains = self.sim.trains[:3]
        self.sim.trains_by_no = {train.train_no: train for train in self.sim.trains}
        shared_route = list(self.sim.trains[0].route)
        for index, train in enumerate(self.sim.trains):
            train.status = TrainStatus.MOVING
            train.predicted_delay_min = 10 + index
            train.prior_delay_min = 4 + index
            train.wait_started_at = None
            if index < 2:
                train.route = shared_route
                train.route_index = 0
                train.progress = 0.25 + index * 0.05
            else:
                train.route_index = 1
                train.progress = 0.15
            train.calculate_priority_score(self.sim.sim_time)

    def _decision_train(self, train_no, train_type, delay, waited_minutes=0):
        train = TrainState({
            "train_no": train_no,
            "name": train_no,
            "type": train_type,
            "route": ["Chennai Central", "Katpadi Junction"],
            "speed_kmph": 60,
        })
        train.predicted_delay_min = delay
        train.prior_delay_min = delay / 2
        if waited_minutes:
            train.status = TrainStatus.WAITING
            train.wait_started_at = self.sim.sim_time - timedelta(minutes=waited_minutes)
        train.calculate_priority_score(self.sim.sim_time)
        return train.to_dict(self.sim.sim_time)

    def _resolve_pair(self, left, right, risk="HIGH"):
        state = {"sim_time": self.sim.sim_time.strftime("%Y-%m-%d %H:%M:%S"), "trains": [left, right]}
        conflict = {
            "conflict_id": f"A <-> B|{left['train_no']},{right['train_no']}",
            "section": "A <-> B",
            "trains_involved": [left["train_no"], right["train_no"]],
            "conflict_status": "predicted",
            "risk": risk,
            "severity": "major" if risk == "HIGH" else "minor",
            "max_predicted_delay": max(left["predicted_delay_min"], right["predicted_delay_min"]),
            "expected_overlap_minutes": 12.0,
            "predicted_arrivals": {left["train_no"]: state["sim_time"], right["train_no"]: state["sim_time"]},
        }
        return resolve_conflicts([conflict], state)[0]

    def _section_train(self, train_no, route, speed=60, delay=0):
        train = TrainState({
            "train_no": train_no,
            "name": train_no,
            "type": "Passenger",
            "route": route,
            "speed_kmph": speed,
        })
        train.predicted_delay_min = delay
        train.calculate_priority_score(self.sim.sim_time)
        return train.to_dict(self.sim.sim_time)

    def _section_state(self, trains):
        return {"sim_time": self.sim.sim_time.strftime("%Y-%m-%d %H:%M:%S"), "trains": trains}

    def test_every_train_has_one_operational_status_and_location(self):
        state = self.sim.get_state()
        for payload in state["trains"]:
            self.assertEqual(payload["status"], payload["operational_status"])
            self.assertIn(payload["location_state"], {"In Section", "Approaching Station", "At Platform", "Completed"})
            self.assertIn("prediction_confidence", payload["prediction_context"])

    def test_priority_explanation_matches_calculation(self):
        conflicts = detect_section_conflicts(self.sim.get_state())
        resolution = resolve_conflicts(conflicts, self.sim.get_state())[0]
        self.assertIn("higher operational priority", resolution["reason"])
        self.assertNotIn("Score = base", resolution["reason"])
        self.assertTrue(conflicts[0]["conflict_id"])
        self.assertEqual(conflicts[0]["conflict_id"], resolution["conflict_id"])
        self.assertEqual(
            round(resolution["winner_priority_score"], 4),
            round(resolution["priority_breakdown"]["score"], 4),
        )
        self.assertEqual(resolution["decision_evidence"]["policy"], "class_first_starvation_aware")

    def test_next_train_selection_is_deterministic(self):
        state_1 = self.sim.get_state()["next_train"]
        state_2 = self.sim.get_state()["next_train"]
        self.assertEqual(state_1["train_no"], state_2["train_no"])
        self.assertEqual(state_1["selection_rule"], state_2["selection_rule"])

    def test_approve_and_reject_change_state_as_expected(self):
        conflict = {
            "section": "A <-> B",
            "trains_involved": [self.sim.trains[0].train_no, self.sim.trains[1].train_no],
            "severity": "minor",
            "max_predicted_delay": max(self.sim.trains[0].predicted_delay_min, self.sim.trains[1].predicted_delay_min),
        }
        resolution = resolve_conflicts([conflict], self.sim.get_state())[0]
        changed = self.sim.apply_controller_decision(
            resolution["decision_id"],
            resolution["winner_train"],
            resolution["held_trains"],
            resolution["section"],
        )
        self.assertEqual(set(changed), set(resolution["held_trains"]))
        for train_no in changed:
            self.assertEqual(self.sim.trains_by_no[train_no].status, TrainStatus.HELD)

        released = self.sim.clear_controller_decision(resolution["decision_id"])
        self.assertEqual(set(released), set(resolution["held_trains"]))
        for train_no in released:
            self.assertEqual(self.sim.trains_by_no[train_no].status, TrainStatus.MOVING)

    def test_logs_are_sorted_newest_first(self):
        from app import database

        database._use_memory_fallback = True
        database._memory_log.clear()
        log_decision("2026-09-05 18:14:00", "section", ["T101"], "check", "older", "simulation")
        log_decision("2026-09-05 18:26:00", "section", ["T102"], "check", "newer", "simulation")
        log_decision("2026-09-05 18:18:00", "section", ["T103"], "check", "middle", "simulation")
        timestamps = [entry["sim_timestamp"] for entry in get_logs()]
        self.assertEqual(timestamps[:3], ["2026-09-05 18:26:00", "2026-09-05 18:18:00", "2026-09-05 18:14:00"])

    def test_conflict_count_matches_active_conflicts(self):
        conflicts = detect_section_conflicts(self.sim.get_state())
        self.sim.observe_conflicts(conflicts)
        analytics = self.sim.get_analytics()
        self.assertEqual(analytics["active_conflicts"], len(self.sim.active_conflict_ids))

    def test_predictive_conflicts_are_separate_from_active_conflicts(self):
        conflicts = detect_all_conflicts(self.sim.get_state())
        predicted = [item for item in conflicts if item["conflict_status"] == "predicted"]
        self.assertTrue(predicted)
        self.assertIn("expected_overlap_minutes", predicted[0])
        self.assertIn("predicted_arrivals", predicted[0])

    def test_same_direction_active_overlap_exposes_movement_evidence(self):
        state = self._section_state([
            self._section_train("T201", ["Salem Junction", "Coimbatore Junction"]),
            self._section_train("T202", ["Salem Junction", "Coimbatore Junction"]),
        ])
        conflict = detect_all_conflicts(state)[0]
        self.assertEqual(conflict["overlap_label"], "ACTIVE SECTION OVERLAP")
        self.assertEqual(conflict["direction_relation"], "same_direction")
        self.assertEqual(conflict["train_movements"]["T201"]["movement_from"], "Salem Junction")
        self.assertEqual(conflict["train_movements"]["T202"]["movement_to"], "Coimbatore Junction")

    def test_opposing_direction_active_overlap_exposes_movement_evidence(self):
        state = self._section_state([
            self._section_train("T301", ["Salem Junction", "Coimbatore Junction"]),
            self._section_train("T302", ["Coimbatore Junction", "Salem Junction"]),
        ])
        conflict = detect_all_conflicts(state)[0]
        self.assertEqual(conflict["direction_relation"], "opposing_direction")
        self.assertEqual(conflict["train_movements"]["T302"]["movement_from"], "Coimbatore Junction")

    def test_incomplete_movement_evidence_is_unknown(self):
        self.assertEqual(
            _direction_relation({
                "T401": {"movement_from": "Salem Junction", "movement_to": "Coimbatore Junction"},
                "T402": {"movement_from": None, "movement_to": None},
            }),
            "unknown",
        )

    def test_active_overlap_suppresses_redundant_projected_pair(self):
        state = self._section_state([
            self._section_train("T501", ["Salem Junction", "Coimbatore Junction"]),
            self._section_train("T502", ["Salem Junction", "Coimbatore Junction"]),
        ])
        conflicts = detect_all_conflicts(state)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["conflict_status"], "active")

    def test_three_active_trains_produce_one_grouped_overlap_without_projected_duplicates(self):
        state = self._section_state([
            self._section_train("T601", ["Salem Junction", "Coimbatore Junction"]),
            self._section_train("T602", ["Salem Junction", "Coimbatore Junction"]),
            self._section_train("T603", ["Salem Junction", "Coimbatore Junction"]),
        ])
        conflicts = detect_all_conflicts(state)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["trains_involved"], ["T601", "T602", "T603"])
        self.assertTrue(conflicts[0]["event_id"].startswith("active|"))

    def test_grouped_conflict_holds_only_trains_related_to_selected_train(self):
        preferred = self._decision_train("T610", "Express", 5)
        related = self._decision_train("T611", "Freight", 6)
        unaffected = self._decision_train("T612", "Passenger", 7)
        state = self._section_state([preferred, related, unaffected])
        conflict = {
            "conflict_id": "A <-> B|T610,T611,T612",
            "section": "A <-> B",
            "trains_involved": ["T610", "T611", "T612"],
            "conflicting_pairs": [["T610", "T611"]],
            "conflict_status": "predicted",
            "risk": "HIGH",
            "severity": "major",
            "max_predicted_delay": 7,
            "expected_overlap_minutes": 12.0,
            "predicted_arrivals": {},
        }

        resolution = resolve_conflicts([conflict], state)[0]

        self.assertEqual(resolution["winner_train"], "T610")
        self.assertEqual(resolution["held_trains"], ["T611"])
        self.assertEqual(resolution["unaffected_trains"], ["T612"])
        self.assertEqual(resolution["decision_evidence"]["selected_train"], "T610")
        self.assertEqual(resolution["decision_evidence"]["trains_requiring_hold"], ["T611"])
        self.assertEqual(resolution["decision_evidence"]["unaffected_trains"], ["T612"])
        self.assertIn("T611", resolution["decision_evidence"]["hold_reasons"])
        self.assertNotIn("T612", resolution["decision_evidence"]["hold_reasons"])

        simulator = Simulator()
        simulator.trains = [
            TrainState({"train_no": train["train_no"], "name": train["train_no"], "type": train["type"], "route": ["A", "B"], "speed_kmph": 60})
            for train in (preferred, related, unaffected)
        ]
        simulator.trains_by_no = {train.train_no: train for train in simulator.trains}
        changed = simulator.apply_controller_decision(
            resolution["decision_id"], resolution["winner_train"], resolution["held_trains"], resolution["section"]
        )
        self.assertEqual(set(changed), {"T611"})
        self.assertEqual(simulator.trains_by_no["T612"].status, TrainStatus.MOVING)
        released = simulator.clear_controller_decision(resolution["decision_id"])
        self.assertEqual(set(released), {"T611"})
        self.assertEqual(simulator.trains_by_no["T612"].status, TrainStatus.MOVING)

    def test_overlapping_projected_pairs_produce_one_consistent_recommendation(self):
        trains = [
            self._decision_train("T630", "Express", 5),
            self._decision_train("T631", "Passenger", 6),
            self._decision_train("T632", "Freight", 7),
        ]
        state = self._section_state(trains)
        base = {
            "section": "A <-> B",
            "conflict_status": "predicted",
            "risk": "HIGH",
            "severity": "major",
            "max_predicted_delay": 7,
            "expected_overlap_minutes": 12.0,
            "predicted_arrivals": {},
        }
        conflicts = [
            {
                **base,
                "conflict_id": "A <-> B|T630,T631",
                "trains_involved": ["T630", "T631"],
                "conflicting_pairs": [["T630", "T631"]],
                "projected_windows": {
                    "T630": {"entry_minutes": 10, "exit_minutes": 30},
                    "T631": {"entry_minutes": 12, "exit_minutes": 28},
                },
            },
            {
                **base,
                "conflict_id": "A <-> B|T630,T632",
                "trains_involved": ["T630", "T632"],
                "conflicting_pairs": [["T630", "T632"]],
                "projected_windows": {
                    "T630": {"entry_minutes": 10, "exit_minutes": 30},
                    "T632": {"entry_minutes": 14, "exit_minutes": 32},
                },
            },
        ]

        resolutions = resolve_conflicts(conflicts, state)

        self.assertEqual(len(resolutions), 1)
        self.assertEqual(resolutions[0]["winner_train"], "T630")
        self.assertEqual(set(resolutions[0]["held_trains"]), {"T631", "T632"})

    def test_approved_hold_releases_when_preferred_train_clears_section(self):
        simulator = Simulator()
        simulator.trains = simulator.trains[:2]
        simulator.trains_by_no = {train.train_no: train for train in simulator.trains}
        for train in simulator.trains:
            train.calculate_priority_score(simulator.sim_time)
        state = simulator.get_state()
        resolution = resolve_conflicts([{
            "section": "Chennai Central <-> Katpadi Junction",
            "trains_involved": [train.train_no for train in simulator.trains],
            "conflicting_pairs": [[train.train_no for train in simulator.trains]],
            "conflict_status": "active",
            "severity": "minor",
            "max_predicted_delay": 0,
        }], state)[0]

        simulator.apply_controller_decision(
            resolution["decision_id"], resolution["winner_train"], resolution["held_trains"], resolution["section"]
        )
        preferred = simulator.trains_by_no[resolution["winner_train"]]
        preferred.route = ["Chennai Central", "Katpadi Junction", "Jolarpettai Junction"]
        preferred.route_index = 1
        released = simulator._release_completed_controller_holds()

        self.assertEqual(set(released), set(resolution["held_trains"]))
        for train_no in resolution["held_trains"]:
            self.assertEqual(simulator.trains_by_no[train_no].status, TrainStatus.MOVING)

    def test_three_train_detector_relationships_drive_two_holds(self):
        state = self._section_state([
            self._section_train("T620", ["Salem Junction", "Coimbatore Junction"]),
            self._section_train("T621", ["Salem Junction", "Coimbatore Junction"]),
            self._section_train("T622", ["Coimbatore Junction", "Salem Junction"]),
        ])
        conflict = detect_section_conflicts(state)[0]
        resolution = resolve_conflicts([conflict], state)[0]

        self.assertEqual(
            set(resolution["held_trains"]),
            {"T620", "T621", "T622"} - {resolution["winner_train"]},
        )
        self.assertEqual(resolution["unaffected_trains"], [])
        self.assertEqual(
            set(resolution["decision_evidence"]["conflict"]["participants"]),
            {"T620", "T621", "T622"},
        )

    def test_three_future_trains_produce_stable_pairwise_projected_overlaps(self):
        state = self._section_state([
            self._section_train("T701", ["Chennai Central", "Katpadi Junction", "Jolarpettai Junction", "Salem Junction", "Coimbatore Junction"], speed=90),
            self._section_train("T702", ["Tiruchirapalli Junction", "Salem Junction", "Coimbatore Junction"], speed=50),
            self._section_train("T703", ["Salem Junction", "Coimbatore Junction"], speed=30),
        ])
        conflicts = [item for item in detect_all_conflicts(state) if item["conflict_status"] == "predicted"]
        self.assertEqual(len(conflicts), 3)
        self.assertEqual(len({item["conflict_id"] for item in conflicts}), 3)
        self.assertTrue(all(item["overlap_label"] == "PROJECTED SECTION OVERLAP" for item in conflicts))
        self.assertTrue(all(item["event_id"].startswith("projected|") for item in conflicts))

    def test_future_pair_remains_when_a_different_current_pair_is_active(self):
        state = self._section_state([
            self._section_train("T801", ["Chennai Central", "Katpadi Junction"]),
            self._section_train("T802", ["Chennai Central", "Katpadi Junction", "Jolarpettai Junction", "Salem Junction", "Coimbatore Junction"], speed=80),
            self._section_train("T803", ["Salem Junction", "Coimbatore Junction"], speed=20),
        ])
        conflicts = detect_all_conflicts(state)
        self.assertTrue(any(item["conflict_status"] == "active" and item["trains_involved"] == ["T801", "T802"] for item in conflicts))
        self.assertTrue(any(item["conflict_status"] == "predicted" and item["trains_involved"] == ["T802", "T803"] for item in conflicts))

    def test_conflict_identity_is_stable_when_train_input_order_changes(self):
        trains = [
            self._section_train("T901", ["Salem Junction", "Coimbatore Junction"]),
            self._section_train("T902", ["Coimbatore Junction", "Salem Junction"]),
        ]
        first = detect_all_conflicts(self._section_state(trains))
        second = detect_all_conflicts(self._section_state(list(reversed(trains))))
        self.assertEqual(
            [(item["conflict_id"], item["event_id"]) for item in first],
            [(item["conflict_id"], item["event_id"]) for item in second],
        )

    def test_direction_evidence_does_not_change_recommendation(self):
        left = self._decision_train("T1001", "Express", 0)
        right = self._decision_train("T1002", "Freight", 50)
        base = self._resolve_pair(left, right)
        state = self._section_state([left, right])
        conflict = {
            "section": "A <-> B", "trains_involved": [left["train_no"], right["train_no"]],
            "conflict_status": "predicted", "risk": "HIGH", "severity": "major",
            "max_predicted_delay": 50, "expected_overlap_minutes": 12.0,
            "predicted_arrivals": {}, "direction_relation": "opposing_direction",
            "train_movements": {left["train_no"]: {"movement_from": "A", "movement_to": "B"}, right["train_no"]: {"movement_from": "B", "movement_to": "A"}},
        }
        with_evidence = resolve_conflicts([conflict], state)[0]
        self.assertEqual(base["winner_train"], with_evidence["winner_train"])
        self.assertEqual(with_evidence["decision_evidence"]["conflict"]["direction_relation"], "opposing_direction")

    def test_controller_approval_uses_legacy_decision_reference_with_direction_evidence(self):
        sim = Simulator()
        sim.trains = [
            TrainState({"train_no": "T1101", "name": "T1101", "type": "Express", "route": ["Salem Junction", "Coimbatore Junction"], "speed_kmph": 60}),
            TrainState({"train_no": "T1102", "name": "T1102", "type": "Freight", "route": ["Salem Junction", "Coimbatore Junction"], "speed_kmph": 60}),
        ]
        sim.trains_by_no = {train.train_no: train for train in sim.trains}
        for train in sim.trains:
            train.calculate_priority_score(sim.sim_time)
        state = sim.get_state()
        resolution = resolve_conflicts(detect_all_conflicts(state), state)[0]
        changed = sim.apply_controller_decision(
            resolution["decision_id"], resolution["winner_train"], resolution["held_trains"], resolution["section"]
        )
        self.assertTrue(resolution["event_id"].startswith("active|"))
        self.assertEqual(resolution["direction_relation"], "same_direction")
        self.assertEqual(changed, resolution["held_trains"])

    def test_future_projection_carries_current_delay_once(self):
        train = self.sim.trains[0].to_dict(self.sim.sim_time)
        train["predicted_delay_min"] = 19.3
        train["progress"] = 0.0
        windows = project_section_windows(train)

        normal_travel = sum(
            get_distance(train["route"][index], train["route"][index + 1]) / train["speed_kmph"] * 60
            for index in range(train["route_index"], len(train["route"]) - 1)
        )
        self.assertAlmostEqual(windows[-1]["exit_minutes"], normal_travel + 19.3, places=6)
        self.assertAlmostEqual(windows[1]["entry_minutes"], windows[0]["exit_minutes"], places=6)
        self.assertTrue(all(
            window["entry_minutes"] <= window["exit_minutes"]
            for window in windows
        ))

    def test_narration_cache_refreshes_when_same_decision_overlap_changes(self):
        from app import main

        resolution = next(
            item for item in resolve_conflicts(detect_all_conflicts(self.sim.get_state()), self.sim.get_state())
            if item["conflict_status"] == "predicted"
        )
        first = deepcopy(resolution)
        first["expected_overlap_minutes"] = 22.3
        first["reason"] = "T101 has higher operational priority; the trains are predicted to overlap for about 22.3 minutes."
        second = deepcopy(first)
        second["expected_overlap_minutes"] = 80.2
        second["reason"] = "T101 has higher operational priority; the trains are predicted to overlap for about 80.2 minutes."

        previous_provider = os.environ.get("LLM_PROVIDER")
        os.environ["LLM_PROVIDER"] = "disabled"
        main.narrated_decisions.clear()
        try:
            first_narration = main._narrate_resolution(first)
            second_narration = main._narrate_resolution(second)
        finally:
            main.narrated_decisions.clear()
            if previous_provider is None:
                os.environ.pop("LLM_PROVIDER", None)
            else:
                os.environ["LLM_PROVIDER"] = previous_provider

        self.assertIn("22.3", first_narration["explanation"])
        self.assertIn("80.2", second_narration["explanation"])
        self.assertNotEqual(first_narration["explanation"], second_narration["explanation"])

    def test_model_status_reports_explicit_fallback_and_feature_contract(self):
        status = get_model_status()
        self.assertTrue(status["fallback"])
        self.assertEqual(status["model"], "Heuristic")
        self.assertEqual(len(MODEL_FEATURE_COLUMNS), 14)

    def test_feature_artifact_matches_runtime_contract(self):
        import joblib

        self.assertEqual(list(joblib.load(FEATURES_PATH)), MODEL_FEATURE_COLUMNS)

    def test_xgboost_artifact_loads_when_enabled(self):
        previous_enabled = os.environ.get("DELAY_MODEL_ENABLED")
        os.environ["DELAY_MODEL_ENABLED"] = "true"
        try:
            load_model()
            status = get_model_status()
            self.assertEqual(status["model"], "XGBoost")
            self.assertFalse(status["fallback"])
        finally:
            os.environ["DELAY_MODEL_ENABLED"] = previous_enabled or "false"
            load_model()

    def test_llm_unavailable_uses_deterministic_fallback(self):
        previous_provider = os.environ.get("LLM_PROVIDER")
        os.environ["LLM_PROVIDER"] = "disabled"
        try:
            fallback = "Recommendation: hold T103; T101 has the higher configured priority."
            result = narrate_decision({"recommendation": {"proceed_train": "T101"}}, fallback)
            self.assertEqual(result["explanation"], fallback)
            self.assertEqual(result["source"], "deterministic_fallback")
            self.assertEqual(result["fallback_reason"], "LLM disabled")
        finally:
            if previous_provider is None:
                os.environ.pop("LLM_PROVIDER", None)
            else:
                os.environ["LLM_PROVIDER"] = previous_provider

    def test_llm_provenance_reports_provider_and_failure(self):
        previous_provider = os.environ.get("LLM_PROVIDER")
        os.environ["LLM_PROVIDER"] = "ollama"
        llm_narration._unavailable_until["ollama"] = 0.0
        try:
            with patch("app.llm_narration._narrate_with_ollama", return_value="Provider explanation."):
                available = narrate_decision({}, "Fallback explanation.")
            with patch("app.llm_narration._narrate_with_ollama", return_value=None):
                unavailable = narrate_decision({}, "Fallback explanation.")
        finally:
            if previous_provider is None:
                os.environ.pop("LLM_PROVIDER", None)
            else:
                os.environ["LLM_PROVIDER"] = previous_provider

        self.assertEqual(available["source"], "ollama")
        self.assertEqual(available["explanation"], "Provider explanation.")
        self.assertEqual(unavailable["source"], "deterministic_fallback")
        self.assertEqual(unavailable["fallback_reason"], "LLM unavailable")

    def test_narration_does_not_change_deterministic_recommendation(self):
        state = self.sim.get_state()
        before = resolve_conflicts(detect_all_conflicts(state), state)
        previous_provider = os.environ.get("LLM_PROVIDER")
        os.environ["LLM_PROVIDER"] = "disabled"
        try:
            narrate_decision({"recommendation": {"proceed_train": before[0]["winner_train"]}}, before[0]["reason"])
            after = resolve_conflicts(detect_all_conflicts(state), state)
        finally:
            if previous_provider is None:
                os.environ.pop("LLM_PROVIDER", None)
            else:
                os.environ["LLM_PROVIDER"] = previous_provider
        self.assertEqual(
            [(item["decision_id"], item["winner_train"], item["held_trains"]) for item in before],
            [(item["decision_id"], item["winner_train"], item["held_trains"]) for item in after],
        )

    def test_conflict_policy_keeps_express_ahead_of_freight_with_small_delay_difference(self):
        resolution = self._resolve_pair(
            self._decision_train("T201", "Express", 5),
            self._decision_train("T202", "Freight", 6),
        )
        self.assertEqual(resolution["winner_train"], "T201")
        self.assertEqual(resolution["decision_evidence"]["selection_rule"], "operational_class")

    def test_conflict_policy_bounds_extreme_freight_delay_against_express(self):
        resolution = self._resolve_pair(
            self._decision_train("T301", "Express", 0),
            self._decision_train("T302", "Freight", 50),
        )
        self.assertEqual(resolution["winner_train"], "T301")
        self.assertEqual(resolution["decision_evidence"]["winner"]["train_type"], "Express")

    def test_conflict_policy_keeps_express_ahead_when_express_is_extremely_delayed(self):
        resolution = self._resolve_pair(
            self._decision_train("T401", "Express", 50),
            self._decision_train("T402", "Freight", 0),
        )
        self.assertEqual(resolution["winner_train"], "T401")

    def test_conflict_policy_keeps_passenger_ahead_of_freight(self):
        resolution = self._resolve_pair(
            self._decision_train("T501", "Passenger", 5),
            self._decision_train("T502", "Freight", 5),
        )
        self.assertEqual(resolution["winner_train"], "T501")

    def test_same_class_uses_delay_then_tiebreaker_deterministically(self):
        delayed = self._resolve_pair(
            self._decision_train("T601", "Passenger", 15),
            self._decision_train("T602", "Passenger", 5),
        )
        tied = self._resolve_pair(
            self._decision_train("T701", "Passenger", 5),
            self._decision_train("T702", "Passenger", 5),
        )
        repeated = self._resolve_pair(
            self._decision_train("T701", "Passenger", 5),
            self._decision_train("T702", "Passenger", 5),
        )
        self.assertEqual(delayed["winner_train"], "T601")
        self.assertEqual(tied["winner_train"], "T702")
        self.assertEqual(tied["decision_id"], repeated["decision_id"])

    def test_starvation_safeguard_overrides_class_after_configured_wait(self):
        resolution = self._resolve_pair(
            self._decision_train("T801", "Express", 0),
            self._decision_train("T802", "Freight", 0, waited_minutes=15),
        )
        self.assertEqual(resolution["winner_train"], "T802")
        self.assertEqual(resolution["decision_evidence"]["selection_rule"], "starvation_safeguard")

    def test_conflict_risk_does_not_change_selection_policy(self):
        low = self._resolve_pair(
            self._decision_train("T901", "Express", 0),
            self._decision_train("T902", "Freight", 50),
            risk="LOW",
        )
        high = self._resolve_pair(
            self._decision_train("T901", "Express", 0),
            self._decision_train("T902", "Freight", 50),
            risk="HIGH",
        )
        self.assertEqual(low["winner_train"], high["winner_train"])
        self.assertEqual(low["decision_evidence"]["selection_rule"], high["decision_evidence"]["selection_rule"])

    def test_initial_active_conflict_remains_class_first_and_deterministic(self):
        full_sim = Simulator()
        full_sim.tick()
        state = full_sim.get_state()
        resolution = next(
            item for item in resolve_conflicts(detect_all_conflicts(state), state)
            if item["conflict_status"] == "active"
            and item["winner_train"] == "T101"
        )
        self.assertEqual(resolution["winner_train"], "T101")
        self.assertEqual(resolution["held_trains"], ["T103"])
        self.assertEqual(resolution["decision_evidence"]["selection_rule"], "operational_class")


if __name__ == "__main__":
    unittest.main()
