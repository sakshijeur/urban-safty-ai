"""Fake live data so the app can be built and shown before the real modules are connected (week 1).

Events use the team's shared event record format (handbook 10.3):
  event_id, type, severity, objects, zone, frame, time, x, y, details, status
Later, replace this file with the real database/event feed. The screens will not change.
"""
import random
from PySide6.QtCore import QObject, Signal, QTimer

# type -> (alert title, possible severities)
EVENT_INFO = {
    "NEAR_MISS": ("NEAR MISS", ["HIGH", "MEDIUM", "CRITICAL"]),
    "VEH_VEH_RISK": ("VEHICLE RISK", ["MEDIUM", "HIGH"]),
    "VEH_PED_RISK": ("PEDESTRIAN RISK", ["MEDIUM", "HIGH"]),
    "SUDDEN_BRAKE": ("SUDDEN BRAKING", ["MEDIUM"]),
    "LANE_CHANGE": ("DANGEROUS LANE CHANGE", ["MEDIUM"]),
    "WRONG_SIDE": ("WRONG SIDE DRIVING", ["HIGH"]),
    "CONGESTION": ("HIGH TRAFFIC DENSITY", ["INFO", "HIGH"]),
    "EMERGENCY_VEH": ("EMERGENCY VEHICLE DETECTED", ["INFO"]),
    "RESTRICTED_ENTRY": ("RESTRICTED ZONE ENTRY", ["MEDIUM"]),
    "POSSIBLE_COLLISION": ("POSSIBLE COLLISION", ["HIGH", "CRITICAL"]),
}
CLASSES = ["Car", "Bike", "Bus", "Truck", "Auto"]
ZONES = ["Zone A", "Zone B", "Zone C", "Zone D"]
COUNTER_OF = {"NEAR_MISS": "near_misses", "SUDDEN_BRAKE": "sudden_braking", "WRONG_SIDE": "wrong_side",
              "RESTRICTED_ENTRY": "restricted_entry", "EMERGENCY_VEH": "emergency_vehicles"}


def format_time(seconds):
    """HH:MM:SS everywhere (handbook 11.4)."""
    return f"{seconds // 3600:02d}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"


ZERO = {"vehicles": 0, "pedestrians": 0, "near_misses": 0, "sudden_braking": 0, "wrong_side": 0,
        "restricted_entry": 0, "emergency_vehicles": 0, "high_risk": 0}
DEMO = {"vehicles": 247, "pedestrians": 36, "near_misses": 8, "sudden_braking": 14, "wrong_side": 3,
        "restricted_entry": 4, "emergency_vehicles": 2, "high_risk": 5}


class EventStore(QObject):
    """Holds all events and counters, and tells the screens when something new happens.
    Real events come from the analysis (add_event / ingest). Demo mode adds fake ones for showing the app."""
    event_added = Signal(dict)
    event_changed = Signal(dict)
    counters_changed = Signal(dict)
    traffic_changed = Signal(str)
    cleared = Signal()
    sessions_changed = Signal()

    def __init__(self, demo=False, db=None):
        super().__init__()
        self.db, self.session_id, self.active_session = db, None, None   # active_session: the run shown on screen
        self.events, self.next_id, self.clock = [], 1, 31 * 60 + 7 - 30   # clock: demo video time in seconds
        self.counters = dict(DEMO if demo else ZERO)
        self.traffic = "HIGH" if demo else "--"
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.add_random_event)
        if demo:
            for _ in range(8):
                self.add_random_event(count=False)

    def start_demo(self, interval_ms=2500):
        self.timer.start(interval_ms)

    def add_event(self, ev, count=True, save=True):
        """Add one event in the shared event record format. Gives it a unique id and saves it to the database."""
        ev = dict(ev)
        ev["event_id"], ev["status"] = self.next_id, ev.get("status", "NEW")
        self.next_id += 1
        if save and self.db and self.session_id:
            ev["db_id"] = self.db.add_event(self.session_id, ev)
        self.events.insert(0, ev)                                  # newest first
        if count:
            key = COUNTER_OF.get(ev["type"])
            if key:
                self.counters[key] += 1
            if ev["severity"] in ("HIGH", "CRITICAL"):
                self.counters["high_risk"] += 1
            self.event_added.emit(ev)
            self.counters_changed.emit(dict(self.counters))
        return ev

    def ingest(self, events):
        """Add a list of events coming from the analysis."""
        for ev in events:
            self.add_event(ev)

    def set_traffic(self, level):
        """Update the Traffic Status badge (LOW / MODERATE / HIGH)."""
        if level != self.traffic:
            self.traffic = level
            self.traffic_changed.emit(level)

    def set_totals(self, vehicles, pedestrians):
        """Update the vehicle / pedestrian counters (approximate unique counts from tracking)."""
        self.counters["vehicles"], self.counters["pedestrians"] = vehicles, pedestrians
        self.counters_changed.emit(dict(self.counters))

    def begin_session(self, source):
        """A new analysis run starts: open a saved session for it."""
        if self.db:
            self.session_id = self.active_session = self.db.new_session(source)
            self.sessions_changed.emit()
        return self.session_id

    def end_session(self, s):
        """The run ended: save totals and the per-object summary. s comes from the analysis worker."""
        if self.db and self.session_id:
            self.db.finish_session(self.session_id, s["frames"], s["duration_s"], s["vehicles"], s["pedestrians"], s["tracks"])
            self.sessions_changed.emit()

    def load_session(self, sid):
        """Show a saved run on every screen (read-only browsing; status changes are still saved)."""
        self.reset()
        self.active_session = sid
        for ev in self.db.events(sid):
            self.add_event(ev, save=False)
        row = self.db.session(sid)
        if row:
            self.set_totals(row["vehicles"], row["pedestrians"])
        self.sessions_changed.emit()

    def reset(self):
        """Clear everything (used when a new analysis starts). Also stops the demo."""
        self.timer.stop()
        self.session_id = self.active_session = None
        self.events, self.next_id = [], 1
        self.counters = dict(ZERO)
        self.traffic = "--"
        self.cleared.emit()
        self.counters_changed.emit(dict(self.counters))
        self.traffic_changed.emit(self.traffic)

    def _objects_for(self, etype):
        a, b = random.randint(1, 60), random.randint(1, 60)
        c1, c2 = random.choice(CLASSES), random.choice(CLASSES)
        if etype in ("NEAR_MISS", "VEH_PED_RISK"):
            return f"{c1} #{a} <-> Ped #{b}"
        if etype in ("VEH_VEH_RISK", "POSSIBLE_COLLISION"):
            return f"{c1} #{a} <-> {c2} #{b}"
        if etype == "EMERGENCY_VEH":
            return f"{random.choice(['Ambulance', 'FireTruck', 'Police'])} #{a}"
        if etype == "CONGESTION":
            return "Heavy traffic"
        return f"{c1} #{a}"

    def add_random_event(self, count=True):
        """Demo only: make one fake event."""
        etype = random.choice(list(EVENT_INFO))
        severity = random.choice(EVENT_INFO[etype][1])
        self.clock += random.randint(2, 5)
        details = {"NEAR_MISS": f"TTC {random.uniform(0.4, 1.9):.1f} s", "SUDDEN_BRAKE": f"-{random.uniform(4, 9):.1f} m/s2",
                   "WRONG_SIDE": f"angle {random.randint(140, 180)} deg"}.get(etype, "")
        ev = {"type": etype, "severity": severity, "objects": self._objects_for(etype), "zone": random.choice(ZONES),
              "frame": self.clock * 25, "time": format_time(self.clock), "x": random.randint(50, 1200),
              "y": random.randint(50, 650), "details": details}
        if count:
            self.counters["vehicles"] += random.randint(0, 3)
            self.counters["pedestrians"] += random.randint(0, 1)
        ev = self.add_event(ev, count)
        if count and random.random() < 0.15:
            self.traffic = random.choice(["LOW", "MODERATE", "HIGH"])
            self.traffic_changed.emit(self.traffic)
        return ev

    def set_status(self, event_id, status):
        """Change an event's status (NEW, ACKNOWLEDGED, INVESTIGATING)."""
        for ev in self.events:
            if ev["event_id"] == event_id:
                ev["status"] = status
                if self.db and ev.get("db_id"):
                    self.db.set_status(ev["db_id"], status)
                self.event_changed.emit(ev)
                return
