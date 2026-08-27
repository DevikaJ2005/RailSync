"""
Simulator Engine — advances a virtual clock, moves trains through the
real-distance network, and drives every train through its state machine
(MOVING -> CHECKING -> WAITING/AT_PLATFORM -> ... -> COMPLETED).
"""

import copy
from datetime import datetime, timedelta
from app.network import STATIONS, TRAINS, get_distance
from app.models import TrainState, TrainStatus
from app.platform_manager import PlatformManager
from app.delay_features import build_delay_features
from app.model_loader import predict_delay


class Simulator:
    def __init__(self):
        self.trains = [TrainState(t) for t in TRAINS]
        self.trains_by_no = {t.train_no: t for t in self.trains}
        self.platform_mgr = PlatformManager(STATIONS)
        self.sim_time = datetime.now().replace(hour=7, minute=0, second=0, microsecond=0)
        self.speed_multiplier = 1.0
        self.paused = False
        self.controller_holds = {}
        self.service_counter = 0
        self.spawn_interval_minutes = 20
        self.next_departure_time = self.sim_time + timedelta(minutes=self.spawn_interval_minutes)
        self.max_active_trains = 30

        self.conflicts_detected = 0
        self.conflicts_resolved = 0
        self.deadlocks_broken = 0
        self.forced_releases = 0
        self.active_conflict_ids = set()

        self.max_wait_minutes = 15  # starvation safeguard threshold
        self.dwell_ticks = 20  # ~40 simulated minutes per platform stop —
        # realistic for a junction halt (crew/loco change), and long enough
        # that trains converging on Salem Jn and Coimbatore Jn (computed to
        # arrive within this window of each other, given their fixed
        # speeds/distances) produce a real, reproducible WAITING state on
        # every run — not a matter of chance

    # ---------------------------------------------------------------
    def pause(self):
        self.paused = True

    def resume(self):
        self.paused = False

    def set_speed(self, multiplier: float):
        self.speed_multiplier = max(0.25, min(multiplier, 10))

    def reset(self):
        """Restart the demo timetable and clear its runtime allocations."""
        self.trains = [TrainState(t) for t in TRAINS]
        self.trains_by_no = {t.train_no: t for t in self.trains}
        self.platform_mgr = PlatformManager(STATIONS)
        self.sim_time = datetime.now().replace(hour=7, minute=0, second=0, microsecond=0)
        self.speed_multiplier = 1.0
        self.paused = False
        self.controller_holds = {}
        self.service_counter = 0
        self.next_departure_time = self.sim_time + timedelta(minutes=self.spawn_interval_minutes)
        self.conflicts_detected = 0
        self.conflicts_resolved = 0
        self.deadlocks_broken = 0
        self.forced_releases = 0
        self.active_conflict_ids = set()

    # ---------------------------------------------------------------
    def _build_delay_feature_contexts(self) -> dict:
        """Snapshot operational features before moving trains for a tick.

        Counts deliberately exclude the train being predicted. This gives the
        model a pre-event view of surrounding traffic and the destination's
        current platform pressure without using an arrival decision that has
        not happened yet.
        """
        section_trains = [
            train
            for train in self.trains
            if train.status not in (TrainStatus.COMPLETED, TrainStatus.AT_PLATFORM)
            and train.current_from != train.current_to
        ]
        contexts = {}
        for train in self.trains:
            if train.status == TrainStatus.COMPLETED:
                continue
            endpoints = frozenset((train.current_from, train.current_to))
            section_occupancy = 0
            nearby_train_count = 0
            for other in section_trains:
                if other.train_no == train.train_no:
                    continue
                other_endpoints = frozenset((other.current_from, other.current_to))
                if other_endpoints == endpoints:
                    section_occupancy += 1
                if endpoints.intersection(other_endpoints):
                    nearby_train_count += 1

            platforms = self.platform_mgr.occupancy.get(train.current_to, {})
            total_platforms = len(platforms)
            occupied_platforms = sum(occupant is not None for occupant in platforms.values())
            available_platforms = total_platforms - occupied_platforms
            contexts[train.train_no] = {
                "section_occupancy": section_occupancy,
                "nearby_train_count": nearby_train_count,
                "destination_platform_occupancy_ratio": (
                    occupied_platforms / total_platforms if total_platforms else 0.0
                ),
                "destination_platform_available_count": available_platforms,
            }
        return contexts

    def observe_conflicts(self, conflicts: list[dict]) -> None:
        """Count conflict onsets once rather than once per API/WebSocket poll."""
        current_ids = {
            f"{conflict['section']}|{','.join(sorted(conflict['trains_involved']))}"
            for conflict in conflicts
        }
        self.conflicts_detected += len(current_ids - self.active_conflict_ids)
        self.active_conflict_ids = current_ids

    def record_controller_resolution(self) -> None:
        """Record a controller-applied rule-based recommendation once."""
        self.conflicts_resolved += 1

    # ---------------------------------------------------------------
    def tick(self):
        if self.paused:
            return

        minutes_advanced = 2 * self.speed_multiplier
        self.sim_time += timedelta(minutes=minutes_advanced)
        self._spawn_due_services()
        self._release_completed_controller_holds()
        feature_contexts = self._build_delay_feature_contexts()

        for train in self.trains:
            if train.status == TrainStatus.COMPLETED:
                continue

            if train.train_no in self.controller_holds:
                if train.status != TrainStatus.HELD:
                    train.status = TrainStatus.HELD
                    train.wait_started_at = self.sim_time
                train.last_event = self.controller_holds[train.train_no]["reason"]
                train.calculate_priority_score(self.sim_time)
                continue

            # The shared feature builder mirrors datasets/generate_dataset.py.
            # It uses the pre-movement state for this tick, never a future
            # platform allocation or arrival outcome.
            if train.status != TrainStatus.AT_PLATFORM:
                features = build_delay_features(
                    train,
                    self.sim_time,
                    feature_contexts.get(train.train_no, {}),
                )
                train.predicted_delay_min = predict_delay(features)
            train.calculate_priority_score(self.sim_time)

            if train.status == TrainStatus.WAITING:
                self._handle_waiting_train(train)
                continue

            if train.status in (TrainStatus.MOVING, TrainStatus.AT_PLATFORM):
                self._advance_train(train, minutes_advanced)

        self._check_deadlocks()
        self._release_completed_controller_holds()

    # ---------------------------------------------------------------
    def _seat_at_platform(self, train: TrainState, station: str, platform: int, event_note: str, dwell_ticks: int | None = None):
        """Single source of truth for putting a train into AT_PLATFORM —
        always sets a real dwell time, so every path (normal arrival,
        event-driven resume, forced release, deadlock break) behaves
        consistently."""
        train.assigned_platform = platform
        train.platform_station = station
        train.status = TrainStatus.AT_PLATFORM
        train.dwell_ticks_remaining = dwell_ticks if dwell_ticks is not None else self.dwell_ticks
        train.wait_started_at = None
        train.last_event = event_note

    def _advance_train(self, train: TrainState, minutes_advanced: float):
        if train.status == TrainStatus.AT_PLATFORM:
            if train.dwell_ticks_remaining > 0:
                train.dwell_ticks_remaining -= 1
                return  # still boarding/alighting, platform stays occupied
            # dwell finished — actually release the platform (this is what
            # triggers event-driven resume for anyone waiting)
            station = train.platform_station or train.current_to
            platform = train.assigned_platform
            if platform is not None:
                self.depart_platform(station, platform)
            train.platform_station = None
            train.assigned_platform = None
            if station == train.current_from and train.progress == 0:
                train.status = TrainStatus.MOVING
                train.last_event = f"Departed {station}"
                return
            self._advance_to_next_section(train)
            return

        distance = get_distance(train.current_from, train.current_to)
        if distance <= 0:
            train.status = TrainStatus.COMPLETED
            return

        total_travel_min = (distance / train.speed_kmph) * 60
        progress_step = minutes_advanced / total_travel_min
        train.progress += progress_step

        if train.progress >= 0.95:
            self._handle_arrival(train)

    def _handle_arrival(self, train: TrainState):
        next_station = train.current_to
        train.progress = 1.0
        train.status = TrainStatus.CHECKING

        if next_station not in train.stops_at:
            # pass-through station — no platform needed, continue immediately
            self._advance_to_next_section(train)
            return

        platform = self.platform_mgr.assign_platform(next_station, train.train_no)
        if platform is not None:
            self._seat_at_platform(train, next_station, platform, f"Arrived at {next_station}, Platform {platform}")
            train.prior_delay_min = train.predicted_delay_min * 0.4  # partial carryover
        else:
            train.status = TrainStatus.WAITING
            train.wait_started_at = self.sim_time
            train.last_event = f"Waiting for a platform at {next_station}"
            self.platform_mgr.add_to_waiting_queue(next_station, train.train_no, self.sim_time)

    def _advance_to_next_section(self, train: TrainState):
        train.route_index += 1
        train.progress = 0.0
        train.assigned_platform = None
        train.platform_station = None
        if train.route_index >= len(train.route) - 1 and train.current_from == train.route[-1]:
            train.status = TrainStatus.COMPLETED
        else:
            train.status = TrainStatus.MOVING

    def _handle_waiting_train(self, train: TrainState):
        waited = train.minutes_waited(self.sim_time)

        # starvation safeguard: force release if waited too long
        if waited >= self.max_wait_minutes:
            station = train.current_to
            platform = self.platform_mgr.assign_platform(station, train.train_no)
            if platform is not None:
                self._seat_at_platform(train, station, platform,
                                        f"Forced release at {station} after {round(waited,1)} min wait")
                self.forced_releases += 1
        # otherwise: stays WAITING, platform_mgr.release_platform() (called when
        # the occupying train departs) is what actually resumes it — event-driven,
        # not polled here.

    def depart_platform(self, station: str, platform: int):
        """Call this when a train AT_PLATFORM finishes boarding and leaves —
        releases the platform and event-driven-resumes the next waiting train.
        The resumed train becomes AT_PLATFORM at the station it was waiting
        for (it does NOT skip past it) — it will depart on a later tick,
        same as any other AT_PLATFORM train."""
        released, resumed, resumed_platform = self.platform_mgr.release_platform(
            station, platform, self.trains_by_no, self.sim_time
        )
        if resumed:
            resumed_train = self.trains_by_no[resumed]
            self._seat_at_platform(resumed_train, station, resumed_platform,
                                    f"Platform {resumed_platform} freed — {resumed} now boarding")
        return released, resumed

    def _check_deadlocks(self):
        """
        Simple two-train mutual-wait deadlock check: if train A is WAITING
        at a station whose platform is occupied by train B, and train B
        (elsewhere) is WAITING on a resource A holds, force-break using
        priority_score.
        """
        waiting_trains = [t for t in self.trains if t.status == TrainStatus.WAITING]
        for t_a in waiting_trains:
            target_station = t_a.current_to
            occupant_no = None
            for plat, occ in self.platform_mgr.occupancy.get(target_station, {}).items():
                if occ:
                    occupant_no = occ
                    break
            if not occupant_no:
                continue
            occupant = self.trains_by_no.get(occupant_no)
            if not occupant or occupant.status != TrainStatus.WAITING:
                continue
            # occupant is itself waiting somewhere — check if it's waiting on t_a's station
            if occupant.current_to == t_a.current_from:
                # mutual block detected — break by priority score
                if t_a.priority_score > occupant.priority_score:
                    winner, loser = t_a, occupant
                else:
                    winner, loser = occupant, t_a
                station = winner.current_to
                platform = self.platform_mgr.assign_platform(station, winner.train_no)
                if platform:
                    self._seat_at_platform(winner, station, platform,
                                            f"Deadlock broken — {winner.train_no} proceeds (higher priority)")
                    self.deadlocks_broken += 1

    # ---------------------------------------------------------------
    def inject_delay(self, train_no: str, extra_minutes: float) -> bool:
        train = self.trains_by_no.get(train_no)
        if not train:
            return False
        train.prior_delay_min += extra_minutes
        return True

    def _spawn_due_services(self):
        while self.sim_time >= self.next_departure_time:
            active_count = sum(1 for t in self.trains if t.status != TrainStatus.COMPLETED)
            if active_count >= self.max_active_trains or not self._spawn_next_service():
                return
            self.next_departure_time += timedelta(minutes=self.spawn_interval_minutes)

    def _spawn_next_service(self) -> bool:
        base = TRAINS[self.service_counter % len(TRAINS)]
        origin = base["route"][0]
        service_no = self.service_counter + 1
        train_def = copy.deepcopy(base)
        train_def["train_no"] = f"{base['train_no']}-{service_no:03d}"
        train_def["name"] = f"{base['name']} #{service_no}"

        platform = self.platform_mgr.assign_platform(origin, train_def["train_no"])
        if platform is None:
            return False

        train = TrainState(train_def)
        self.trains.append(train)
        self.trains_by_no[train.train_no] = train
        self._seat_at_platform(
            train,
            origin,
            platform,
            f"Scheduled service boarding at {origin}, Platform {platform}",
            dwell_ticks=5,
        )
        self.service_counter += 1
        return True

    def apply_controller_decision(self, decision_id: str, winner_train: str, held_trains: list[str], section: str):
        """Hold lower-priority trains until the approved winner clears the conflict section."""
        applied = []
        for train_no in held_trains:
            train = self.trains_by_no.get(train_no)
            if not train or train.status == TrainStatus.COMPLETED:
                continue
            self.controller_holds[train_no] = {
                "decision_id": decision_id,
                "winner_train": winner_train,
                "section": section,
                "reason": f"Controller hold: giving {winner_train} movement authority through {section}",
            }
            train.status = TrainStatus.HELD
            train.wait_started_at = self.sim_time
            train.last_event = self.controller_holds[train_no]["reason"]
            applied.append(train_no)
        return applied

    def apply_manual_hold(self, train_no: str) -> bool:
        """Apply a reversible controller hold to a moving simulated train."""
        train = self.trains_by_no.get(train_no)
        if not train or train.status in (TrainStatus.COMPLETED, TrainStatus.AT_PLATFORM, TrainStatus.WAITING):
            return False
        self.controller_holds[train_no] = {
            "decision_id": f"manual:{train_no}",
            "winner_train": None,
            "section": self._section_name(train),
            "reason": f"Manual controller hold applied to {train_no}",
            "manual": True,
        }
        train.status = TrainStatus.HELD
        train.wait_started_at = self.sim_time
        train.last_event = self.controller_holds[train_no]["reason"]
        return True

    def release_manual_hold(self, train_no: str) -> bool:
        hold = self.controller_holds.get(train_no)
        if not hold or not hold.get("manual"):
            return False
        self._release_controller_hold(train_no, "Manual controller hold released")
        return True

    def clear_controller_decision(self, decision_id: str):
        released = []
        for train_no, hold in list(self.controller_holds.items()):
            if hold["decision_id"] == decision_id:
                self._release_controller_hold(train_no, "Controller hold cleared")
                released.append(train_no)
        return released

    def _release_completed_controller_holds(self):
        for train_no, hold in list(self.controller_holds.items()):
            if hold.get("manual"):
                continue
            winner = self.trains_by_no.get(hold["winner_train"])
            if (
                not winner
                or winner.status in (TrainStatus.COMPLETED, TrainStatus.AT_PLATFORM)
                or self._section_name(winner) != hold["section"]
            ):
                self._release_controller_hold(
                    train_no,
                    f"Controller hold released: {hold['winner_train']} cleared {hold['section']}",
                )

    def _release_controller_hold(self, train_no: str, reason: str):
        self.controller_holds.pop(train_no, None)
        train = self.trains_by_no.get(train_no)
        if train and train.status == TrainStatus.HELD:
            train.status = TrainStatus.MOVING
            train.wait_started_at = None
            train.last_event = reason

    def _section_name(self, train: TrainState) -> str:
        endpoints = sorted([train.current_from, train.current_to])
        return f"{endpoints[0]} <-> {endpoints[1]}"

    def get_state(self) -> dict:
        return {
            "sim_time": self.sim_time.strftime("%Y-%m-%d %H:%M"),
            "paused": self.paused,
            "speed_multiplier": self.speed_multiplier,
            "trains": [t.to_dict(self.sim_time) for t in self.trains],
            "platforms": self.platform_mgr.snapshot(),
            "controller_holds": self.controller_holds,
            "next_departure_time": self.next_departure_time.strftime("%Y-%m-%d %H:%M"),
            "next_departure_service": self._next_service_preview(),
        }

    def get_analytics(self) -> dict:
        active_predicted_delay = sum(
            train.predicted_delay_min
            for train in self.trains
            if train.status != TrainStatus.COMPLETED
        )
        return {
            "conflicts_detected": self.conflicts_detected,
            "controller_resolutions_applied": self.conflicts_resolved,
            "deadlocks_broken": self.deadlocks_broken,
            "forced_releases": self.forced_releases,
            "active_conflicts": len(self.active_conflict_ids),
            "active_predicted_delay_min": round(active_predicted_delay, 1),
        }

    def _next_service_preview(self) -> dict:
        base = TRAINS[self.service_counter % len(TRAINS)]
        return {
            "train_no": f"{base['train_no']}-{self.service_counter + 1:03d}",
            "name": base["name"],
            "origin": base["route"][0],
            "destination": base["route"][-1],
        }
