"""
Platform Manager — tracks which platform at each station is occupied by
which train, and handles the event-driven "resume" behavior: when a
platform frees up, the highest-priority waiting train is automatically
assigned to it, no polling delay.
"""


class PlatformManager:
    def __init__(self, stations: dict):
        # occupancy[station][platform_number] = train_no or None
        self.occupancy = {
            name: {i: None for i in range(1, info["platforms"] + 1)}
            for name, info in stations.items()
        }
        # waiting_queue[station] = list of train_no currently WAITING there
        self.waiting_queue = {name: [] for name in stations}
        self.events = []  # log of {type, station, train_no, detail}

    def is_any_platform_free(self, station: str) -> bool:
        return any(v is None for v in self.occupancy.get(station, {}).values())

    def get_free_platform(self, station: str):
        for platform, occupant in self.occupancy.get(station, {}).items():
            if occupant is None:
                return platform
        return None

    def assign_platform(self, station: str, train_no: str) -> int | None:
        platform = self.get_free_platform(station)
        if platform is None:
            return None
        self.occupancy[station][platform] = train_no
        if train_no in self.waiting_queue.get(station, []):
            self.waiting_queue[station].remove(train_no)
        return platform

    def release_platform(self, station: str, platform: int, trains_by_no: dict, sim_time):
        """
        Releases a platform, then immediately checks the waiting queue for
        that station — if anyone's waiting, the highest-priority train is
        assigned right away. Returns (released_train_no, resumed_train_no,
        resumed_platform_no) — the caller (Simulator) is responsible for
        updating the resumed train's own state/status fields.
        """
        released_train = self.occupancy[station].get(platform)
        self.occupancy[station][platform] = None

        resumed_train_no = None
        resumed_platform = None
        queue = self.waiting_queue.get(station, [])
        if queue:
            # highest priority_score first
            queue_sorted = sorted(
                queue,
                key=lambda tn: trains_by_no[tn].priority_score if tn in trains_by_no else 0,
                reverse=True,
            )
            next_train_no = queue_sorted[0]
            assigned = self.assign_platform(station, next_train_no)
            if assigned:
                resumed_train_no = next_train_no
                resumed_platform = assigned
                self.events.append({
                    "type": "resume",
                    "station": station,
                    "train_no": next_train_no,
                    "detail": f"Platform {assigned} freed by {released_train} — {next_train_no} resumes",
                })

        return released_train, resumed_train_no, resumed_platform

    def add_to_waiting_queue(self, station: str, train_no: str, sim_time):
        if train_no not in self.waiting_queue[station]:
            self.waiting_queue[station].append(train_no)
            self.events.append({
                "type": "held",
                "station": station,
                "train_no": train_no,
                "detail": f"{train_no} held — no free platform at {station}",
            })

    def get_waiting_queue(self, station: str) -> list:
        return list(self.waiting_queue.get(station, []))

    def pop_events(self) -> list:
        ev = self.events
        self.events = []
        return ev

    def snapshot(self) -> dict:
        return {
            station: {
                "platforms": {str(p): occ for p, occ in plats.items()},
                "waiting_queue": self.waiting_queue.get(station, []),
            }
            for station, plats in self.occupancy.items()
        }
