"""Comprehensive test suite for the RailSync MiniMax LLM Explanation & Narration Layer.

Validates all 15+ operational scenarios required by the architecture:
1. Express vs Passenger
2. Passenger vs Freight
3. Longest-wait scenario
4. Starvation safeguard scenario
5. Active conflict
6. Projected conflict
7. Single hold
8. Multiple necessary holds
9. No-conflict operation
10. Platform unavailable event
11. Approved recommendation
12. Rejected recommendation
13. MiniMax unavailable (deterministic fallback)
14. MiniMax produces contradictory/hallucinated output (validation rejection)
15. Cached old explanation vs new decision (cache invalidation)
16. Deterministic engine immutability (decision invariant)
17. Zero generic boilerplate invariant
"""

import os
import sys
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("DELAY_MODEL_ENABLED", "false")
os.environ.setdefault("FIREBASE_ENABLED", "false")

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app import llm_narration
from app.llm_narration import (
    build_deterministic_fallback,
    narrate_decision,
    narrate_log_event,
    validate_explanation,
)
from app.models import TrainState, TrainStatus
from app.resolver import resolve_conflicts
from app.simulator import Simulator


@contextmanager
def env_override(**kwargs):
    old = {}
    for k, v in kwargs.items():
        old[k] = os.environ.get(k)
        os.environ[k] = v
    try:
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


class MiniMaxNarrationScenariosTest(unittest.TestCase):
    def setUp(self):
        self.sim_time = datetime(2026, 9, 19, 10, 0, 0)

    def _train(self, train_no: str, train_type: str, delay: float = 0.0, waited_min: float = 0.0):
        t = TrainState({
            "train_no": train_no,
            "name": train_no,
            "type": train_type,
            "route": ["Coimbatore Junction", "Salem Junction"],
            "speed_kmph": 60,
        })
        t.predicted_delay_min = delay
        if waited_min > 0:
            t.status = TrainStatus.WAITING
            t.wait_started_at = self.sim_time - timedelta(minutes=waited_min)
        t.calculate_priority_score(self.sim_time)
        return t.to_dict(self.sim_time)

    # 1. Express vs Passenger
    def test_01_express_vs_passenger(self):
        exp = self._train("T107-017", "Express", delay=2.0)
        pas = self._train("T104-014", "Passenger", delay=4.0)
        state = {"sim_time": self.sim_time.strftime("%Y-%m-%d %H:%M:%S"), "trains": [exp, pas]}
        conflict = {
            "conflict_id": "Coimbatore Junction → Salem Junction|T107-017,T104-014",
            "section": "Coimbatore Junction → Salem Junction",
            "trains_involved": ["T107-017", "T104-014"],
            "conflict_status": "active",
            "severity": "major",
            "max_predicted_delay": 4.0,
        }
        res = resolve_conflicts([conflict], state)[0]
        self.assertEqual(res["winner_train"], "T107-017")
        self.assertEqual(res["held_trains"], ["T104-014"])
        self.assertEqual(res["decision_evidence"]["reason_type"], "operational_class")

        with env_override(LLM_PROVIDER="disabled"):
            narration = narrate_decision(res)
        explanation = narration["explanation"]
        self.assertIn("T107-017", explanation)
        self.assertIn("higher operational priority", explanation)
        self.assertIn("T104-014", explanation)
        self.assertNotIn("under the configured operating policy", explanation)

    # 2. Passenger vs Freight
    def test_02_passenger_vs_freight(self):
        pas = self._train("T201-001", "Passenger", delay=0.0)
        frt = self._train("T202-002", "Freight", delay=0.0)
        state = {"sim_time": self.sim_time.strftime("%Y-%m-%d %H:%M:%S"), "trains": [pas, frt]}
        conflict = {
            "conflict_id": "A → B|T201-001,T202-002",
            "section": "A → B",
            "trains_involved": ["T201-001", "T202-002"],
            "conflict_status": "active",
            "severity": "minor",
            "max_predicted_delay": 0.0,
        }
        res = resolve_conflicts([conflict], state)[0]
        self.assertEqual(res["winner_train"], "T201-001")
        self.assertEqual(res["decision_evidence"]["reason_type"], "operational_class")

        fallback = build_deterministic_fallback(res)
        self.assertIn("T201-001", fallback)
        self.assertIn("higher operational priority", fallback)
        self.assertIn("T202-002", fallback)
        self.assertNotIn("configured operating policy", fallback)

    # 3. Longest-wait scenario (same class)
    def test_03_longest_wait_scenario(self):
        pas1 = self._train("T301-001", "Passenger", delay=5.0, waited_min=8.0)
        pas2 = self._train("T302-002", "Passenger", delay=5.0, waited_min=2.0)
        state = {"sim_time": self.sim_time.strftime("%Y-%m-%d %H:%M:%S"), "trains": [pas1, pas2]}
        conflict = {
            "conflict_id": "A → B|T301-001,T302-002",
            "section": "A → B",
            "trains_involved": ["T301-001", "T302-002"],
            "conflict_status": "active",
            "severity": "minor",
            "max_predicted_delay": 5.0,
        }
        res = resolve_conflicts([conflict], state)[0]
        self.assertEqual(res["winner_train"], "T301-001")
        self.assertEqual(res["decision_evidence"]["reason_type"], "longest_wait")

        fallback = build_deterministic_fallback(res)
        self.assertIn("waiting the longest", fallback)
        self.assertIn("T301-001", fallback)
        self.assertIn("T302-002", fallback)

    # 4. Starvation safeguard scenario (Freight waited >= 15 min overrides Express)
    def test_04_starvation_safeguard(self):
        exp = self._train("T401-001", "Express", delay=0.0, waited_min=0.0)
        frt = self._train("T402-002", "Freight", delay=0.0, waited_min=16.0)
        state = {"sim_time": self.sim_time.strftime("%Y-%m-%d %H:%M:%S"), "trains": [exp, frt]}
        conflict = {
            "conflict_id": "A → B|T401-001,T402-002",
            "section": "A → B",
            "trains_involved": ["T401-001", "T402-002"],
            "conflict_status": "active",
            "severity": "major",
            "max_predicted_delay": 0.0,
        }
        res = resolve_conflicts([conflict], state)[0]
        self.assertEqual(res["winner_train"], "T402-002")
        self.assertEqual(res["decision_evidence"]["reason_type"], "starvation_safeguard")

        fallback = build_deterministic_fallback(res)
        self.assertIn("extended period", fallback)
        self.assertIn("T402-002", fallback)
        self.assertIn("T401-001", fallback)
        self.assertNotIn("starvation safeguard score", fallback)

    # 5. Active conflict ("currently sharing logical section")
    def test_05_active_conflict_phrasing(self):
        exp = self._train("T501", "Express")
        pas = self._train("T502", "Passenger")
        context = {
            "conflict_type": "active",
            "section": "Salem Junction → Coimbatore Junction",
            "selected_train": "T501",
            "hold_trains": ["T502"],
            "reason_type": "operational_class",
        }
        text = build_deterministic_fallback(context)
        self.assertIn("T501", text)
        self.assertIn("T502", text)
        self.assertIn("higher operational priority", text)
        self.assertIn("recommended to wait while the conflicting movement is resolved", text)

    # 6. Projected conflict ("expected to use the same logical section at overlapping times")
    def test_06_projected_conflict_phrasing(self):
        context = {
            "conflict_type": "projected",
            "section": "Salem Junction → Coimbatore Junction",
            "selected_train": "T601",
            "hold_trains": ["T602"],
            "reason_type": "operational_class",
        }
        text = build_deterministic_fallback(context)
        self.assertIn("expected to use the same logical section", text)
        self.assertIn("overlapping times", text)
        self.assertIn("T601", text)
        self.assertIn("T602", text)

    # 7. Single hold
    def test_07_single_hold(self):
        context = {
            "conflict_type": "active",
            "section": "A → B",
            "selected_train": "T701",
            "hold_trains": ["T702"],
            "reason_type": "operational_class",
        }
        text = build_deterministic_fallback(context)
        self.assertIn("T702 is recommended to wait", text)
        self.assertNotIn("were recommended", text)

    # 8. Multiple necessary holds
    def test_08_multiple_necessary_holds(self):
        context = {
            "conflict_type": "active",
            "section": "A → B",
            "selected_train": "T801",
            "hold_trains": ["T802", "T803"],
            "unaffected_trains": ["T804"],
            "reason_type": "operational_class",
        }
        text = build_deterministic_fallback(context)
        self.assertIn("T802, T803 are recommended to wait", text)
        self.assertNotIn("All other trains", text)
        self.assertNotIn("T804", text)

    # 9. No-conflict operation
    def test_09_no_conflict_clear(self):
        context = {
            "event_type": "OPERATIONAL_EVENT",
            "reason": "Operations clear. Timetable operating normally.",
        }
        text = build_deterministic_fallback(context)
        self.assertIn("Operations clear", text)

    # 10. Platform unavailable operational event
    def test_10_platform_unavailable_event(self):
        context = {
            "event_type": "PLATFORM_UNAVAILABLE",
            "station": "Salem Junction",
            "hold_trains": ["T101"],
            "reason_type": "platform_unavailable",
            "reason": "T101 held — no free platform at Salem Junction",
        }
        text = build_deterministic_fallback(context)
        self.assertIn("T101 was held because no platform was available at Salem Junction", text)
        self.assertIn("The train will remain waiting until a platform becomes available", text)

    # 11. Approved recommendation log narration
    def test_11_approved_recommendation(self):
        context = {
            "event_type": "CONTROLLER_ACTION",
            "section": "Coimbatore Junction → Salem Junction",
            "selected_train": "T107-017",
            "hold_trains": ["T104-014"],
            "reason_type": "operational_class",
            "controller_action": "approved",
        }
        text = build_deterministic_fallback(context)
        self.assertIn("T107-017 was recommended to continue", text)
        self.assertIn("higher operational priority", text)
        self.assertIn("T104-014 was recommended to wait", text)
        self.assertIn("controller approved the recommendation and the hold was applied", text)

    # 12. Rejected recommendation log narration
    def test_12_rejected_recommendation(self):
        context = {
            "event_type": "CONTROLLER_ACTION",
            "section": "Coimbatore Junction → Salem Junction",
            "selected_train": "T107-017",
            "hold_trains": ["T104-014"],
            "reason_type": "operational_class",
            "controller_action": "rejected",
        }
        text = build_deterministic_fallback(context)
        self.assertIn("T107-017 was recommended to continue", text)
        self.assertIn("controller rejected the recommendation, so no hold was applied by this recommendation", text)
        self.assertNotIn("hold was applied.", text)

    # 13. MiniMax unavailable (deterministic fallback used)
    def test_13_minimax_unavailable_uses_deterministic_fallback(self):
        context = {
            "section": "A → B",
            "selected_train": "T101",
            "hold_trains": ["T102"],
            "reason_type": "operational_class",
            "conflict_type": "active",
        }
        with env_override(LLM_PROVIDER="openrouter", OPENROUTER_API_KEY="fake_key"):
            with patch("app.llm_narration._narrate_with_openrouter", return_value=None):
                result = narrate_decision(context)
        self.assertEqual(result["source"], "deterministic_fallback")
        self.assertIn("T101", result["explanation"])
        self.assertNotIn("configured operating policy", result["explanation"])

    # 14. MiniMax produces contradictory / hallucinated output
    def test_14_validation_rejects_hallucination_and_falls_back(self):
        context = {
            "section": "A → B",
            "selected_train": "T101",
            "hold_trains": ["T102"],
            "reason_type": "operational_class",
            "conflict_type": "active",
            "trains_involved": ["T101", "T102"],
        }
        # Case A: Collision claim
        self.assertFalse(validate_explanation("Collision avoided between T101 and T102.", context))
        # Case B: Physical track claim
        self.assertFalse(validate_explanation("T101 proceeds on physical track 1.", context))
        # Case C: Invented train ID
        self.assertFalse(validate_explanation("T101 proceeds while T999 waits.", context))
        # Case D: Mathematical score leak
        self.assertFalse(validate_explanation("T101 has a score of 30 and T102 has score of 10.", context))
        # Case E: Internal technical terms
        self.assertFalse(validate_explanation("XGBoost algorithm selected T101 based on priority score.", context))

        # End-to-end: narration rejects invalid LLM output and falls back
        with env_override(LLM_PROVIDER="openrouter", OPENROUTER_API_KEY="fake_key"):
            with patch("app.llm_narration._narrate_with_openrouter", return_value="XGBoost algorithm selected T101."):
                result = narrate_decision(context)
        self.assertEqual(result["source"], "deterministic_fallback")
        self.assertIn("T101", result["explanation"])

    # 15. Cached old explanation vs new decision
    def test_15_cache_invalidation_on_fact_change(self):
        from app import main

        res1 = {
            "decision_id": "SEC|T101|T102",
            "section": "A → B",
            "winner_train": "T101",
            "held_trains": ["T102"],
            "conflict_status": "predicted",
            "expected_overlap_minutes": 10.0,
            "reason": "T101 has higher operational priority; projected overlap 10.0 min.",
            "decision_evidence": {"reason_type": "operational_class"},
            "train_predictions": {},
            "action": "proceed",
        }
        res2 = dict(res1)
        res2["expected_overlap_minutes"] = 45.0
        res2["reason"] = "T101 has higher operational priority; projected overlap 45.0 min."

        key1 = main._narration_cache_key(res1)
        key2 = main._narration_cache_key(res2)
        self.assertNotEqual(key1, key2, "Cache key must change when overlap or explanatory facts change")

    # 16. Deterministic engine immutability
    def test_16_decision_engine_immutability(self):
        sim = Simulator()
        state = sim.get_state()
        before_resolutions = resolve_conflicts(sim.observe_conflicts([]) or [], state)

        # Calling narration must never modify simulation state or conflict resolution
        with env_override(LLM_PROVIDER="disabled"):
            narrate_decision({"recommendation": {"proceed_train": "T101"}})

        after_state = sim.get_state()
        self.assertEqual(
            [t["train_no"] for t in state["trains"]],
            [t["train_no"] for t in after_state["trains"]],
        )

    # 17. Zero generic boilerplate invariant
    def test_17_no_generic_operating_policy_phrase(self):
        contexts = [
            {"selected_train": "T107-017", "hold_trains": ["T104-014"], "reason_type": "operational_class", "conflict_type": "active"},
            {"selected_train": "T107-017", "hold_trains": ["T104-014"], "reason_type": "longest_wait", "conflict_type": "active"},
            {"selected_train": "T107-017", "hold_trains": ["T104-014"], "reason_type": "starvation_safeguard", "conflict_type": "active"},
            {"selected_train": "T107-017", "hold_trains": ["T104-014"], "controller_action": "approved"},
            {"selected_train": "T107-017", "hold_trains": ["T104-014"], "controller_action": "rejected"},
            {"event_type": "PLATFORM_UNAVAILABLE", "hold_trains": ["T101"], "station": "Salem Junction"},
        ]
        for ctx in contexts:
            text = build_deterministic_fallback(ctx)
            self.assertNotIn(
                "under the configured operating policy",
                text.lower(),
                f"Generic boilerplate found in: {text}",
            )

    # 18. Manual hold log narration (Step 6 scenario 4)
    def test_18_manual_hold_event(self):
        context = {
            "event_type": "HOLD",
            "train_no": "T101",
            "station": "Salem Junction",
            "section": "Coimbatore Junction → Salem Junction",
            "hold_trains": ["T101"],
            "reason_type": "manual_hold",
        }
        text = build_deterministic_fallback(context)
        self.assertIn("T101", text)
        self.assertIn("controller instruction", text)
        self.assertIn("waiting", text)
        sentences = [s.strip() for s in text.split(".") if s.strip()]
        self.assertLessEqual(len(sentences), 3)

    # 19. Resume log narration (Step 6 scenario 5)
    def test_19_resume_event(self):
        context = {
            "event_type": "RESUME",
            "train_no": "T101",
            "station": "Salem Junction",
            "section": "Coimbatore Junction → Salem Junction",
            "hold_trains": ["T101"],
            "reason_type": "manual_resume",
        }
        text = build_deterministic_fallback(context)
        self.assertIn("T101", text)
        self.assertIn("resumed movement", text)
        self.assertIn("clearance", text)
        sentences = [s.strip() for s in text.split(".") if s.strip()]
        self.assertLessEqual(len(sentences), 3)

    # 20. Insufficient evidence fallback (Step 6 negative constraint)
    def test_20_insufficient_evidence_fallback(self):
        context = {}
        fallback = build_deterministic_fallback(context)
        self.assertEqual(
            fallback,
            "RailSync cannot provide a more specific explanation from the available simulation data.",
        )
        with env_override(LLM_PROVIDER="disabled"):
            res = narrate_decision(context)
        self.assertEqual(
            res["explanation"],
            "RailSync cannot provide a more specific explanation from the available simulation data.",
        )

    # 21. Strict negative constraints rejection (Step 6 negative constraint)
    def test_21_strict_negative_constraints_rejected(self):
        base_ctx = {
            "section": "A → B",
            "selected_train": "T101",
            "hold_trains": ["T102"],
            "trains_involved": ["T101", "T102"],
            "conflict_type": "active",
        }
        forbidden_samples = [
            "T101 was chosen by deterministic train-number tie-breaker while T102 waits.",
            "T101 proceeds due to operational_class priority over T102.",
            "T101 proceeds because starvation safeguard was triggered for T102.",
            "T101 priority score 0.83 beats 0.41 for T102.",
            "T101 proceeds under decision_id 42 while T102 waits.",
            "T101 selected for event_id 999 while T102 waits.",
            "Projected occupancy window cleared for T101 while T102 waits.",
            "T101 won on model feature weights while T102 waits.",
            "XGBoost prediction assigned priority to T101 over T102.",
            "T101 proceeds because red signal was displayed for T102.",
            "T101 and T102 head-on collision was prevented by RailSync.",
            "T101 proceeds because physical track switches are clear for T102.",
            "RailSync guarantees railway safety for T101 and T102.",
        ]
        for sample in forbidden_samples:
            self.assertFalse(
                validate_explanation(sample, base_ctx),
                f"Validation failed to reject forbidden phrasing: {sample}",
            )

    # 22. Authoritative decision immunity on LLM failure / hallucination (Step 6 immunity requirement)
    def test_22_authoritative_decision_immunity(self):
        res = {
            "decision_id": "SEC|T101|T102",
            "section": "A → B",
            "winner_train": "T101",
            "held_trains": ["T102"],
            "action": "proceed",
            "conflict_status": "active",
            "decision_evidence": {"reason_type": "operational_class", "selected_train": "T101", "trains_requiring_hold": ["T102"]},
        }
        original_winner = res["winner_train"]
        original_held = list(res["held_trains"])
        original_action = res["action"]
        original_id = res["decision_id"]

        with env_override(LLM_PROVIDER="openrouter", OPENROUTER_API_KEY="fake_key"):
            with patch("app.llm_narration._narrate_with_openrouter", return_value="CRITICAL COLLISION: T102 proceeds instead!"):
                narration = narrate_decision(res)

        # Explanation fell back to deterministic template
        self.assertEqual(narration["source"], "deterministic_fallback")
        self.assertIn("T101", narration["explanation"])
        self.assertIn("T102", narration["explanation"])

        # Authoritative decision is 100% unchanged
        self.assertEqual(res["winner_train"], original_winner)
        self.assertEqual(res["held_trains"], original_held)
        self.assertEqual(res["action"], original_action)
        self.assertEqual(res["decision_id"], original_id)


if __name__ == "__main__":
    unittest.main()

