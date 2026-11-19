"""Risk rules: near miss, vehicle-vehicle risk, vehicle-pedestrian risk, possible collision,
sudden braking, dangerous lane change and congestion. All limits are in config.py.

Input each frame: a list of tracks, each a dict with tid, cls, x1, y1, x2, y2, gx, gy (ground point),
vx, vy (pixels per second), speed. Output: events in the shared event record format."""
import math
from collections import deque
import config as cfg
from wrong_side import format_time

TITLES = {"NEAR_MISS": "NEAR MISS", "VEH_VEH_RISK": "VEHICLE RISK", "VEH_PED_RISK": "PEDESTRIAN RISK",
          "POSSIBLE_COLLISION": "POSSIBLE COLLISION", "SUDDEN_BRAKE": "SUDDEN BRAKING",
          "LANE_CHANGE": "DANGEROUS LANE CHANGE", "CONGESTION": "HIGH TRAFFIC DENSITY",
          "WRONG_SIDE": "WRONG SIDE DRIVING"}
INF = float("inf")


def _h(a): return max(1.0, a["y2"] - a["y1"])
def _w(a): return max(1.0, a["x2"] - a["x1"])
def _foot(a):
    """The strip of an object that touches the road. Two objects only touch if their feet touch."""
    return {"x1": a["x1"], "x2": a["x2"], "y1": a["gy"] - cfg.FOOT_FRACTION * _h(a), "y2": a["gy"]}


def _name(a): return f"{cfg.DISPLAY_NAME.get(a['cls'], a['cls'])} #{a['tid']}"


def _gap(a, b):
    """Edge-to-edge distance between two boxes in pixels (0 if they touch or overlap)."""
    dx = max(0.0, max(a["x1"], b["x1"]) - min(a["x2"], b["x2"]))
    dy = max(0.0, max(a["y1"], b["y1"]) - min(a["y2"], b["y2"]))
    return math.hypot(dx, dy)


def _overlap(a, b):
    """Overlapping area as a share of the smaller box."""
    iw = min(a["x2"], b["x2"]) - max(a["x1"], b["x1"])
    ih = min(a["y2"], b["y2"]) - max(a["y1"], b["y1"])
    return 0.0 if iw <= 0 or ih <= 0 else iw * ih / min(_w(a) * _h(a), _w(b) * _h(b))


def _rides(p, b):
    """Is person p sitting on bike b? (the person's box overlaps the bike and their feet are at the bike's level)"""
    bw, bh, ph = _w(b), _h(b), _h(p)
    cx = (p["x1"] + p["x2"]) / 2
    if not (b["x1"] - 0.2 * bw <= cx <= b["x2"] + 0.2 * bw):
        return False
    if not (b["y1"] + 0.3 * bh <= p["y2"] <= b["y2"] + 0.2 * ph):
        return False
    return _overlap(p, b) >= 0.2


class RiderFinder:
    """Finds the 'persons' that are really riding a bike, so they are not counted or treated as pedestrians."""
    def __init__(self):
        self.score = {}

    def update(self, tracks):
        """Returns the set of track ids of riders. A person scores when overlapping a bike or moving too fast to be walking."""
        bikes = [a for a in tracks if a["cls"] == "bike"]
        seen, riders = set(), set()
        for p in tracks:
            if p["cls"] != "person":
                continue
            on = any(_rides(p, b) for b in bikes) or p["speed"] > cfg.PED_MAX_SPEED_H * _h(p)
            s = self.score.get(p["tid"], 0)
            self.score[p["tid"]] = min(10, s + 2) if on else max(0, s - 1)
            seen.add(p["tid"])
            if self.score[p["tid"]] >= cfg.RIDER_SCORE:
                riders.add(p["tid"])
        for tid in [k for k in self.score if k not in seen]:           # tracks that vanished fade out
            self.score[tid] -= 1
            if self.score[tid] <= 0:
                del self.score[tid]
        return riders


class RiskEngine:
    def __init__(self, zones, fps):
        self.fps = fps
        self.lanes = [l["points"] for l in zones.get("lane_lines", []) if len(l.get("points", [])) >= 2]
        self.last, self.speeds, self.sides, self.marks, self.counts = {}, {}, {}, {}, {}
        self.level, self._cand, self._since, self._next = "--", "LOW", 0.0, 0.0

    def level_of(self, tid, t):
        """'danger' / 'warning' while an object is part of a recent risk (used to color its box)."""
        m = self.marks.get(tid)
        return m[0] if m and t < m[1] else None

    def _mark(self, tid, level, t):
        old = self.marks.get(tid)
        if not old or t >= old[1] or level == "danger":
            self.marks[tid] = (level, t + 1.5)

    def _ready(self, key, t):
        """Cooldown: false if this same event was raised a moment ago."""
        if t - self.last.get(key, -1e9) < cfg.EVENT_COOLDOWN_S:
            return False
        self.last[key] = t
        return True

    RANK = {"VEH_VEH_RISK": 1, "VEH_PED_RISK": 1, "NEAR_MISS": 2, "POSSIBLE_COLLISION": 3}

    def _escalates(self, pair, typ, t):
        """One event per pair per encounter, unless it gets MORE serious (risk -> near miss -> collision)."""
        last = self.last.get(("pair",) + pair)
        rank = self.RANK[typ]
        if last and t - last[0] < cfg.EVENT_COOLDOWN_S and rank <= last[1]:
            return False
        self.last[("pair",) + pair] = (t, rank)
        return True

    @staticmethod
    def _event(typ, sev, objects, x, y, frame_no, t, zone, details):
        return {"type": typ, "severity": sev, "objects": objects, "zone": zone, "frame": frame_no,
                "time": format_time(t), "x": round(x, 1), "y": round(y, 1), "details": details, "status": "NEW"}

    def update(self, frame_no, t, tracks, zone_of=lambda x, y: "-"):
        """Check all rules for this frame. Returns the new events."""
        mature = [a for a in tracks if a.get("age", 999) >= cfg.RISK_MIN_AGE]       # new, unreliable tracks are ignored
        return (self._pairs(frame_no, t, mature, zone_of) + self._braking(frame_no, t, mature, zone_of)
                + self._lanes(frame_no, t, mature, zone_of) + self._congestion(frame_no, t, tracks))

    @staticmethod
    def _in_corridor(veh, ped):
        """Is the pedestrian inside the strip in front of the moving vehicle?"""
        speed = math.hypot(veh["vx"], veh["vy"])
        if speed < 0.5 * _h(veh):
            return False
        ux, uy = veh["vx"] / speed, veh["vy"] / speed
        rx, ry = ped["gx"] - veh["gx"], ped["gy"] - veh["gy"]
        along, lateral = rx * ux + ry * uy, abs(rx * uy - ry * ux)
        return 0 < along < max(2 * _h(veh), cfg.CORRIDOR_SECONDS * speed) and lateral < cfg.CORRIDOR_WIDTH * max(_w(veh), 0.5 * _h(veh))

    def _pairs(self, frame_no, t, tracks, zone_of):
        out, seen = [], set()
        for i, a in enumerate(tracks):
            for b in tracks[i + 1:]:
                pa, pb = a["cls"] == "person", b["cls"] == "person"
                if pa and pb:
                    continue
                h, big = min(_h(a), _h(b)), max(_h(a), _h(b))
                fa, fb = _foot(a), _foot(b)
                gap = _gap(fa, fb)                              # distance between the feet, not between the boxes
                if gap > cfg.PAIR_SEARCH * big:
                    continue
                rx, ry = b["gx"] - a["gx"], b["gy"] - a["gy"]
                dist = math.hypot(rx, ry) or 1.0
                rvx, rvy = b["vx"] - a["vx"], b["vy"] - a["vy"]
                ov = _overlap(fa, fb)
                if ov > 0.1 and math.hypot(rvx, rvy) < cfg.RIDER_REL_H * h:
                    continue                                     # a rider on a bike, or a duplicate box
                closing = -(rx * rvx + ry * rvy) / dist          # pixels per second the two are approaching
                ttc = gap / closing if closing > cfg.MIN_CLOSING_H * h else INF
                typ = sev = None
                detail = ""
                if ov >= cfg.COLLISION_OVERLAP and closing > cfg.MIN_CLOSING_H * h:
                    typ, sev, detail = "POSSIBLE_COLLISION", "HIGH", f"overlap {ov * 100:.0f}%"
                elif 0 < gap < cfg.NEAR_MISS_GAP * h and ttc < cfg.TTC_MEDIUM:
                    typ, sev, detail = "NEAR_MISS", ("HIGH" if ttc < cfg.TTC_HIGH else "MEDIUM"), f"TTC {ttc:.1f} s, gap {gap / h:.1f} heights, closing {closing / h:.1f} heights/s"
                elif pa or pb:
                    veh, ped = (b, a) if pa else (a, b)
                    if self._in_corridor(veh, ped) and ttc < cfg.VP_TTC:
                        typ, sev, detail = "VEH_PED_RISK", ("HIGH" if ttc < cfg.TTC_MEDIUM else "MEDIUM"), f"TTC {ttc:.1f} s"
                elif gap < 1.5 * cfg.NEAR_MISS_GAP * h and ttc < cfg.VV_TTC:
                    typ, sev, detail = "VEH_VEH_RISK", ("HIGH" if ttc < cfg.TTC_HIGH else "MEDIUM"), f"TTC {ttc:.1f} s"
                if typ is None:
                    continue
                ck = (typ, min(a["tid"], b["tid"]), max(a["tid"], b["tid"]))
                seen.add(ck)
                self.counts[ck] = self.counts.get(ck, 0) + 1
                if self.counts[ck] < cfg.CONFIRM_FRAMES:        # must hold for several frames in a row
                    continue
                level = "danger" if sev == "HIGH" else "warning"
                self._mark(a["tid"], level, t)
                self._mark(b["tid"], level, t)
                if self._escalates((min(a["tid"], b["tid"]), max(a["tid"], b["tid"])), typ, t):
                    mx, my = (a["gx"] + b["gx"]) / 2, (a["gy"] + b["gy"]) / 2
                    out.append(self._event(typ, sev, f"{_name(a)} <-> {_name(b)}", mx, my, frame_no, t, zone_of(mx, my), detail))
        self.counts = {k: v for k, v in self.counts.items() if k in seen}      # a break resets the count
        return out

    def _braking(self, frame_no, t, tracks, zone_of):
        out, seen = [], set()
        lo, hi = cfg.BRAKE_WINDOW
        for a in tracks:
            if a["cls"] == "person":
                continue
            seen.add(a["tid"])
            hist = self.speeds.setdefault(a["tid"], deque(maxlen=int(self.fps * 1.5) + 2))
            hist.append((t, a["speed"]))
            h = _h(a)
            past = [s for tt, s in hist if t - hi <= tt <= t - lo]
            if not past:
                continue
            peak = max(past)
            if peak < cfg.BRAKE_MIN_SPEED_H * h or a["speed"] > peak * (1 - cfg.BRAKE_DROP):
                continue
            if any(o is not a and o["cls"] != "person" and _gap(_foot(a), _foot(o)) < 0.6 * h for o in tracks):
                continue                                          # slowing in a queue is normal
            self._mark(a["tid"], "warning", t)
            if self._ready(("brake", a["tid"]), t):
                out.append(self._event("SUDDEN_BRAKE", "MEDIUM", _name(a), a["gx"], a["gy"], frame_no, t,
                                       zone_of(a["gx"], a["gy"]), f"speed -{(1 - a['speed'] / peak) * 100:.0f}%"))
        for tid in [k for k in self.speeds if k not in seen]:
            del self.speeds[tid]
        return out

    def _lanes(self, frame_no, t, tracks, zone_of):
        out = []
        for li, pts in enumerate(self.lanes):
            (x0, y0), (x1, y1) = pts[0], pts[-1]
            dx, dy = x1 - x0, y1 - y0
            n = math.hypot(dx, dy) or 1.0
            for a in tracks:
                if a["cls"] == "person":
                    continue
                side = (dx * (a["gy"] - y0) - dy * (a["gx"] - x0)) / n    # signed distance from the lane line
                prev = self.sides.get((a["tid"], li))
                self.sides[(a["tid"], li)] = side
                if prev is None or prev * side >= 0:
                    continue
                if abs(a["vx"] * dy - a["vy"] * dx) / n < cfg.LANE_LATERAL_H * _h(a):
                    continue                                          # slow drift, not a sharp lane change
                close = any(o is not a and o["cls"] != "person" and _gap(a, o) < 1.5 * _h(a) for o in tracks)
                self._mark(a["tid"], "danger" if close else "warning", t)
                if self._ready(("lane", a["tid"]), t):
                    out.append(self._event("LANE_CHANGE", "HIGH" if close else "MEDIUM", _name(a), a["gx"], a["gy"],
                                           frame_no, t, zone_of(a["gx"], a["gy"]), "close to another vehicle" if close else "fast lateral move"))
        return out

    def _congestion(self, frame_no, t, tracks):
        if t < self._next:
            return []
        self._next = t + 1.0
        veh = [a for a in tracks if a["cls"] != "person"]
        n = len(veh)
        stopped = sum(a["speed"] < cfg.STOPPED_H * _h(a) for a in veh)
        frac = stopped / n if n else 0.0
        if n >= cfg.CONG_HIGH_COUNT and frac >= cfg.CONG_STOPPED_FRAC:
            cand = "HIGH"
        elif n >= cfg.CONG_MOD_COUNT or (n >= 4 and frac >= 0.5):
            cand = "MODERATE"
        else:
            cand = "LOW"
        if self.level == "--":                                     # first look: start neutral, then earn the level
            self.level, self._cand, self._since = "LOW", cand, t
        if cand != self._cand:
            self._cand, self._since = cand, t
        if cand != self.level and t - self._since >= cfg.CONG_HOLD_S:     # hysteresis: the level must hold for a while
            self.level = cand
            if cand == "HIGH":
                return [self._event("CONGESTION", "HIGH", "Heavy traffic", 0, 0, frame_no, t, "-", f"{n} vehicles, {stopped} stopped")]
        return []
