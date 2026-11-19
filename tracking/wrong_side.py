"""Wrong-side driving detection (Member 2).

A vehicle inside a road area is wrong-side if its heading points against the area's
expected direction (angle difference above WRONG_SIDE_ANGLE) for WRONG_SIDE_FRAMES frames
in a row. One event is made per vehicle.
"""
import cv2
import numpy as np
import config as cfg
from geometry import heading_deg

EVENT_FIELDS = ["event_id", "type", "severity", "objects", "zone", "frame", "time", "x", "y", "details", "status"]


def format_time(t):
    """Seconds -> HH:MM:SS (video time)."""
    t = int(t)
    return f"{t // 3600:02d}:{(t % 3600) // 60:02d}:{t % 60:02d}"


def angle_difference(a, b):
    """Smallest difference between two headings, 0 to 180 degrees."""
    return abs((a - b + 180) % 360 - 180)


class WrongSideDetector:
    def __init__(self, zones):
        self.areas = []
        for r in zones.get("road_directions", []):
            vx, vy = r["expected_vector"]
            self.areas.append({"name": r.get("zone", "Zone A"),
                               "poly": np.array(r["polygon"], dtype=np.float32),
                               "angle": heading_deg(vx, vy)})
        self.count, self.flagged, self.next_event = {}, set(), 1

    def area_of(self, x, y):
        """The road area that contains this ground point, or None."""
        for a in self.areas:
            if cv2.pointPolygonTest(a["poly"], (float(x), float(y)), False) >= 0:
                return a
        return None

    def is_flagged(self, tid):
        return tid in self.flagged

    def update(self, frame_no, t, tid, cls, gx, gy, heading, moved_px):
        """Call once per object per frame. Returns an event dict the moment one is raised."""
        if cls == "person" or tid in self.flagged or not self.areas:
            return None
        area = self.area_of(gx, gy)
        if area is None:
            self.count[tid] = 0
            return None
        if moved_px < cfg.MIN_MOVE_PX:
            return None                                   # not really moving: leave the count alone
        diff = angle_difference(heading, area["angle"])
        self.count[tid] = self.count.get(tid, 0) + 1 if diff >= cfg.WRONG_SIDE_ANGLE else 0
        if self.count[tid] < cfg.WRONG_SIDE_FRAMES:
            return None
        self.flagged.add(tid)
        ev = {"event_id": self.next_event, "type": "WRONG_SIDE", "severity": "HIGH",
              "objects": f"{cfg.DISPLAY_NAME.get(cls, cls)} #{tid}", "zone": area["name"],
              "frame": frame_no, "time": format_time(t), "x": round(gx, 1), "y": round(gy, 1),
              "details": f"angle {diff:.0f} deg", "status": "NEW"}
        self.next_event += 1
        return ev
