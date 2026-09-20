import os
import sys
import unittest
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path

os.environ.setdefault("DELAY_MODEL_ENABLED", "false")
os.environ.setdefault("FIREBASE_ENABLED", "false")

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.conflict_detection import detect_all_conflicts, detect_predictive_conflicts, detect_section_conflicts
from app.models import TrainState, TrainStatus
from app.platform_manager import PlatformManager
from app.resolver import resolve_conflicts
from app.simulator import Simulator


class Step4ConflictResolutionAuditTests(unittest.TestCase):
    def setUp(self):
        self.sim = Simulator()

    def _create_train(self, train_no, train_type, route, route_index=0, progress=0.2, speed=60, delay=0.0):
        t = TrainState({
            "train_no": train_no,
            "name": f"Train {train_no}",
            "type": train_type,
            "route": route,
            "speed_kmph": speed,
            "stops_at": list(route),
        })
        t.route_index = route_index
        t.progress = progress
        t.status = TrainStatus.MOVING
        t.predicted_delay_min = delay
        t.prior_delay_min = delay
        t.calculate_priority_score(self.sim.sim_time)
        return t

    def test_scenario_a_ten_trains_no_conflict(self):
        """Scenario A: 10 trains operating with no conflicts.
        Expected: 0 conflicts detected, 0 holds applied.
        """
        # Assign 10 trains to distinct sections or directions that do not overlap
        sections = [
            ["Chennai Central", "Katpadi Junction"],
            ["Katpadi Junction", "Jolarpettai Junction"],
            ["Jolarpettai Junction", "Salem Junction"],
            ["Salem Junction", "Tiruchirapalli Junction"],
            ["Tiruchirapalli Junction", "Madurai Junction"],
            ["Chennai Central", "Villupuram Junction"],
            ["Villupuram Junction", "Tiruchirapalli Junction"],
            ["Salem Junction", "Coimbatore Junction"],
        ]
        trains = []
        for i in range(10):
            route = sections[i % len(sections)]
            trains.append(self._create_train(f"T{100 + i}", "Express" if i % 2 == 0 else "Passenger", route, progress=0.1 * ((i % 5) + 1)))

        # Ensure no two trains share the exact same section simultaneously
        # Let's give each train a unique current section
        all_unique_sections = [
            ["Chennai Central", "Katpadi Junction"],
            ["Katpadi Junction", "Jolarpettai Junction"],
            ["Jolarpettai Junction", "Salem Junction"],
            ["Salem Junction", "Tiruchirapalli Junction"],
            ["Tiruchirapalli Junction", "Madurai Junction"],
            ["Chennai Central", "Villupuram Junction"],
            ["Villupuram Junction", "Tiruchirapalli Junction"],
            ["Salem Junction", "Coimbatore Junction"],
            ["Katpadi Junction", "Chennai Central"],
            ["Madurai Junction", "Tiruchirapalli Junction"],
        ]
        # In RailSync sections are undirected: sorted(from, to). Let's pick 10 disjoint sections:
        # We only have 8 physical sections in the network, so let's put 8 trains on 8 distinct sections,
        # and 2 trains at platforms or completed.
        trains = []
        for i, sec in enumerate(sections):
            trains.append(self._create_train(f"T10{i+1}", "Express", sec, progress=0.3))
        # Add 2 more trains: 1 at platform, 1 completed
        t9 = self._create_train("T109", "Passenger", ["Chennai Central", "Katpadi Junction"])
        t9.status = TrainStatus.AT_PLATFORM
        t9.platform_station = "Chennai Central"
        t9.assigned_platform = 1
        trains.append(t9)

        t10 = self._create_train("T110", "Freight", ["Salem Junction", "Coimbatore Junction"])
        t10.status = TrainStatus.COMPLETED
        trains.append(t10)

        self.sim.trains = trains
        self.sim.trains_by_no = {t.train_no: t for t in trains}

        state = self.sim.get_state()
        conflicts = detect_section_conflicts(state)
        resolutions = resolve_conflicts(conflicts, state)

        self.assertEqual(len(conflicts), 0, "Expected 0 active conflicts when trains occupy disjoint sections")
        self.assertEqual(len(resolutions), 0, "Expected 0 resolutions when no conflicts exist")
        self.assertEqual(len(self.sim.controller_holds), 0, "Expected 0 holds applied")
        # Verify all moving trains continue moving
        moving_trains = [t for t in self.sim.trains if t.status == TrainStatus.MOVING]
        self.assertEqual(len(moving_trains), 8)

    def test_scenario_b_two_trains_conflict_only_necessary_train_waits(self):
        """Scenario B: 10 trains operating, only 2 conflict.
        Expected: Winner proceeds, only 1 necessary train waits, other 8 continue.
        """
        trains = [
            # T101 (Express) and T108 (Freight) share Salem <-> Coimbatore
            self._create_train("T101", "Express", ["Salem Junction", "Coimbatore Junction"], progress=0.4),
            self._create_train("T108", "Freight", ["Salem Junction", "Coimbatore Junction"], progress=0.2),
            # 8 other trains in distinct sections
            self._create_train("T102", "Express", ["Chennai Central", "Katpadi Junction"], progress=0.5),
            self._create_train("T103", "Passenger", ["Katpadi Junction", "Jolarpettai Junction"], progress=0.3),
            self._create_train("T104", "Freight", ["Jolarpettai Junction", "Salem Junction"], progress=0.6),
            self._create_train("T105", "Express", ["Salem Junction", "Tiruchirapalli Junction"], progress=0.4),
            self._create_train("T106", "Passenger", ["Tiruchirapalli Junction", "Madurai Junction"], progress=0.2),
            self._create_train("T107", "Freight", ["Chennai Central", "Villupuram Junction"], progress=0.5),
            self._create_train("T109", "Passenger", ["Villupuram Junction", "Tiruchirapalli Junction"], progress=0.7),
            # T110 at platform at Katpadi
            TrainState({
                "train_no": "T110",
                "name": "Train T110",
                "type": "Express",
                "route": ["Katpadi Junction", "Jolarpettai Junction"],
                "speed_kmph": 60,
                "stops_at": ["Katpadi Junction", "Jolarpettai Junction"],
            }),
        ]
        trains[-1].status = TrainStatus.AT_PLATFORM
        trains[-1].platform_station = "Katpadi Junction"
        trains[-1].assigned_platform = 2
        self.sim.trains = trains
        self.sim.trains_by_no = {t.train_no: t for t in trains}

        state = self.sim.get_state()
        conflicts = detect_section_conflicts(state)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["trains_involved"], ["T101", "T108"])

        resolutions = resolve_conflicts(conflicts, state)
        self.assertEqual(len(resolutions), 1)
        res = resolutions[0]
        self.assertEqual(res["winner_train"], "T101")
        self.assertEqual(res["held_trains"], ["T108"])
        self.assertEqual(res["unaffected_trains"], [])

        # Apply controller decision
        changed = self.sim.apply_controller_decision(
            res["decision_id"], res["winner_train"], res["held_trains"], res["section"]
        )
        self.assertEqual(changed, ["T108"])

        # Check train statuses: ONLY T108 is held, all others remain MOVING
        self.assertEqual(self.sim.trains_by_no["T108"].status, TrainStatus.HELD)
        self.assertEqual(self.sim.trains_by_no["T101"].status, TrainStatus.MOVING)
        for other_no in ["T102", "T103", "T104", "T105", "T106", "T107", "T109"]:
            self.assertEqual(
                self.sim.trains_by_no[other_no].status,
                TrainStatus.MOVING,
                f"Train {other_no} should remain MOVING and not be cascaded into hold",
            )
        self.assertEqual(self.sim.trains_by_no["T110"].status, TrainStatus.AT_PLATFORM)
        for other_no in ["T102", "T103", "T104", "T105", "T106", "T107", "T109", "T110"]:
            self.assertNotEqual(
                self.sim.trains_by_no[other_no].status,
                TrainStatus.HELD,
                f"Train {other_no} must not be held",
            )

    def test_scenario_c_three_trains_logical_section_no_blind_mass_hold(self):
        """Scenario C: 3 trains in a conflict group / section.
        Expected: Decision selects a winner to proceed; system does NOT blindly hold all 3.
        If a train is unrelated to the conflict pair, it is marked unaffected.
        """
        # Case 1: 3 trains share logical section. Express proceeds, 2 lower classes wait.
        t1 = self._create_train("T201", "Express", ["Salem Junction", "Coimbatore Junction"], progress=0.6)
        t2 = self._create_train("T202", "Passenger", ["Salem Junction", "Coimbatore Junction"], progress=0.4)
        t3 = self._create_train("T203", "Freight", ["Salem Junction", "Coimbatore Junction"], progress=0.2)

        self.sim.trains = [t1, t2, t3]
        self.sim.trains_by_no = {t.train_no: t for t in [t1, t2, t3]}

        state = self.sim.get_state()
        conflicts = detect_section_conflicts(state)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(set(conflicts[0]["trains_involved"]), {"T201", "T202", "T203"})

        resolutions = resolve_conflicts(conflicts, state)
        self.assertEqual(len(resolutions), 1)
        res = resolutions[0]
        # Crucial check: T201 is winner, NOT all 3 held!
        self.assertEqual(res["winner_train"], "T201")
        self.assertNotIn("T201", res["held_trains"])
        self.assertEqual(len(res["held_trains"]), 2)

        # Case 2: Grouped conflict where 1 train is unaffected by winner
        # e.g. T201 (Express) conflicts with T202 (Passenger), while T203 (Freight) was only paired with T202
        conflict_partial = {
            "conflict_id": "SEC|T201,T202,T203",
            "section": "Salem Junction <-> Coimbatore Junction",
            "trains_involved": ["T201", "T202", "T203"],
            "conflicting_pairs": [["T201", "T202"]],  # T203 is not in pair with winner T201
            "conflict_status": "predicted",
            "risk": "HIGH",
            "severity": "major",
            "max_predicted_delay": 5,
        }
        res_partial = resolve_conflicts([conflict_partial], state)[0]
        self.assertEqual(res_partial["winner_train"], "T201")
        self.assertEqual(res_partial["held_trains"], ["T202"])
        self.assertEqual(res_partial["unaffected_trains"], ["T203"])

    def test_scenario_d_projected_conflict_recommendation_only_no_automatic_hold(self):
        """Scenario D: Projected conflict only.
        Expected: Generates a recommendation, but does NOT apply an automatic controller hold.
        """
        # T301 and T302 heading toward Salem Junction <-> Coimbatore Junction in the future
        t1 = self._create_train("T301", "Express", ["Chennai Central", "Katpadi Junction", "Jolarpettai Junction", "Salem Junction", "Coimbatore Junction"], route_index=2, progress=0.8, speed=80)
        t2 = self._create_train("T302", "Passenger", ["Tiruchirapalli Junction", "Salem Junction", "Coimbatore Junction"], route_index=0, progress=0.5, speed=60)

        self.sim.trains = [t1, t2]
        self.sim.trains_by_no = {t.train_no: t for t in [t1, t2]}

        state = self.sim.get_state()
        active = detect_section_conflicts(state)
        predicted = detect_predictive_conflicts(state)

        self.assertEqual(len(active), 0, "No active conflict expected yet")
        self.assertGreaterEqual(len(predicted), 1, "Projected conflict expected")

        resolutions = resolve_conflicts(predicted, state)
        self.assertGreaterEqual(len(resolutions), 1)
        self.assertEqual(resolutions[0]["conflict_status"], "predicted")

        # Crucial check: Simulator state must have 0 holds automatically applied!
        self.assertEqual(len(self.sim.controller_holds), 0)
        self.assertEqual(t1.status, TrainStatus.MOVING)
        self.assertEqual(t2.status, TrainStatus.MOVING)

    def test_scenario_e_controller_rejects_recommendation_no_hold_applied(self):
        """Scenario E: Controller rejects recommendation.
        Expected: Decision is rejected/cleared and no hold is applied solely because recommendation existed.
        """
        t1 = self._create_train("T401", "Express", ["Salem Junction", "Coimbatore Junction"], progress=0.4)
        t2 = self._create_train("T402", "Freight", ["Salem Junction", "Coimbatore Junction"], progress=0.2)
        self.sim.trains = [t1, t2]
        self.sim.trains_by_no = {t.train_no: t for t in [t1, t2]}

        state = self.sim.get_state()
        resolution = resolve_conflicts(detect_section_conflicts(state), state)[0]

        # Controller rejects: calls clear_controller_decision
        released = self.sim.clear_controller_decision(resolution["decision_id"])
        self.assertEqual(released, [])
        self.assertEqual(len(self.sim.controller_holds), 0)
        self.assertEqual(t1.status, TrainStatus.MOVING)
        self.assertEqual(t2.status, TrainStatus.MOVING)

    def test_scenario_f_controller_approves_only_recommended_train_held(self):
        """Scenario F: Controller approves.
        Expected: Only the recommended train becomes held, winner proceeds.
        """
        t1 = self._create_train("T501", "Express", ["Salem Junction", "Coimbatore Junction"], progress=0.5)
        t2 = self._create_train("T502", "Freight", ["Salem Junction", "Coimbatore Junction"], progress=0.2)
        self.sim.trains = [t1, t2]
        self.sim.trains_by_no = {t.train_no: t for t in [t1, t2]}

        state = self.sim.get_state()
        resolution = resolve_conflicts(detect_section_conflicts(state), state)[0]

        applied = self.sim.apply_controller_decision(
            resolution["decision_id"], resolution["winner_train"], resolution["held_trains"], resolution["section"]
        )

        self.assertEqual(applied, ["T502"])
        self.assertEqual(self.sim.trains_by_no["T502"].status, TrainStatus.HELD)
        self.assertEqual(self.sim.trains_by_no["T501"].status, TrainStatus.MOVING)
        self.assertIn("giving T501 movement authority", self.sim.controller_holds["T502"]["reason"])

    def test_scenario_g_held_train_resumes_when_conflict_disappears(self):
        """Scenario G: Held train's conflict disappears.
        Expected: Train resumes according to simulation rules (HELD -> MOVING).
        """
        t1 = self._create_train("T601", "Express", ["Salem Junction", "Coimbatore Junction", "Tiruchirapalli Junction"], progress=0.8)
        t2 = self._create_train("T602", "Freight", ["Salem Junction", "Coimbatore Junction"], progress=0.2)
        self.sim.trains = [t1, t2]
        self.sim.trains_by_no = {t.train_no: t for t in [t1, t2]}

        state = self.sim.get_state()
        resolution = resolve_conflicts(detect_section_conflicts(state), state)[0]
        self.sim.apply_controller_decision(
            resolution["decision_id"], resolution["winner_train"], resolution["held_trains"], resolution["section"]
        )
        self.assertEqual(t2.status, TrainStatus.HELD)

        # Winner advances out of section
        t1.route_index = 1
        t1.progress = 0.1
        self.sim.tick()

        # Check: t2 should be released from controller hold and restored to MOVING
        self.assertEqual(t2.status, TrainStatus.MOVING)
        self.assertNotIn("T602", self.sim.controller_holds)

    def test_scenario_h_platform_unavailable_is_platform_waiting_not_section_conflict(self):
        """Scenario H: Platform unavailable at station.
        Expected: Train enters WAITING status, not HELD. Event is platform_waiting, NOT section conflict.
        """
        # Salem Junction has 1 platform. Put a train at platform.
        occupant = self._create_train("T701", "Express", ["Salem Junction", "Coimbatore Junction"])
        self.sim.platform_mgr.assign_platform("Salem Junction", "T701")
        occupant.status = TrainStatus.AT_PLATFORM
        occupant.platform_station = "Salem Junction"
        occupant.assigned_platform = 1

        # Second train arrives at Salem Junction from Jolarpettai
        arriving = self._create_train("T702", "Passenger", ["Jolarpettai Junction", "Salem Junction"], progress=0.98)

        self.sim.trains = [occupant, arriving]
        self.sim.trains_by_no = {t.train_no: t for t in [occupant, arriving]}

        # Trigger arrival
        self.sim._handle_arrival(arriving)

        # Arriving train must be WAITING, NOT HELD
        self.assertEqual(arriving.status, TrainStatus.WAITING)
        self.assertIn("Waiting for a platform at Salem Junction", arriving.last_event)

        # Crucial check: Section conflict detector MUST NOT flag WAITING or AT_PLATFORM trains
        state = self.sim.get_state()
        conflicts = detect_section_conflicts(state)
        self.assertEqual(len(conflicts), 0, "Platform waiting must not create a section conflict")

        # Platform manager event check
        events = self.sim.platform_mgr.pop_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["type"], "held")
        self.assertIn("no free platform at Salem Junction", events[0]["detail"])


if __name__ == "__main__":
    unittest.main()
