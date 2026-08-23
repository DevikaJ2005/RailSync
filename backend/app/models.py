"""
Train state machine. Every train is always in exactly one of these
states — this is what makes the map show trains genuinely waiting,
not just abstractly "delayed".
"""

from enum import Enum


class TrainStatus(str, Enum):
    MOVING = "moving"
    CHECKING = "checking"
    WAITING = "waiting"
    HELD = "held"
    AT_PLATFORM = "at_platform"
    COMPLETED = "completed"


TYPE_BASE_PRIORITY = {"Express": 30, "Passenger": 20, "Freight": 10}


class TrainState:
    def __init__(self, train_def: dict):
        self.train_no = train_def["train_no"]
        self.name = train_def["name"]
        self.type = train_def["type"]
        self.route = train_def["route"]
        self.stops_at = set(train_def.get("stops_at", train_def["route"]))
        self.speed_kmph = train_def["speed_kmph"]

        self.route_index = 0
        self.progress = 0.0  # 0.0 -> 1.0 along current section
        self.status = TrainStatus.MOVING
        self.assigned_platform = None
        self.platform_station = None
        self.dwell_ticks_remaining = 0  # how many more ticks it stays AT_PLATFORM
        self.prior_delay_min = 0.0
        self.predicted_delay_min = 0.0
        self.wait_started_at = None  # simulated datetime
        self.priority_score = 0.0
        self.last_event = None  # human-readable, for the map tooltip

    @property
    def current_from(self):
        return self.route[self.route_index] if self.route_index < len(self.route) else self.route[-1]

    @property
    def current_to(self):
        if self.route_index + 1 < len(self.route):
            return self.route[self.route_index + 1]
        return self.route[-1]

    @property
    def is_finished(self):
        return self.route_index >= len(self.route) - 1 and self.progress >= 1.0

    def minutes_waited(self, sim_time) -> float:
        if not self.wait_started_at:
            return 0.0
        return (sim_time - self.wait_started_at).total_seconds() / 60.0

    def calculate_priority_score(self, sim_time) -> float:
        base = TYPE_BASE_PRIORITY.get(self.type, 15)
        delay_factor = self.predicted_delay_min * 0.5
        wait_factor = self.minutes_waited(sim_time) * 2.0
        # deterministic tiny tiebreaker so no two trains can ever tie exactly
        tiebreak = int("".join(filter(str.isdigit, self.train_no)) or 0) * 0.001
        self.priority_score = round(base + delay_factor + wait_factor + tiebreak, 4)
        return self.priority_score

    def to_dict(self, sim_time=None):
        return {
            "train_no": self.train_no,
            "name": self.name,
            "type": self.type,
            "route": self.route,
            "route_index": self.route_index,
            "speed_kmph": self.speed_kmph,
            "from": self.current_from,
            "to": self.current_to,
            "progress": round(self.progress, 3),
            "status": self.status.value,
            "assigned_platform": self.assigned_platform,
            "platform_station": self.platform_station,
            "prior_delay_min": round(self.prior_delay_min, 1),
            "predicted_delay_min": round(self.predicted_delay_min, 1),
            "priority_score": self.priority_score,
            "minutes_waited": round(self.minutes_waited(sim_time), 1) if sim_time else 0,
            "last_event": self.last_event,
        }
