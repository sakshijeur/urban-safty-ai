"""Tracking module (Member 2): frame in, track records out.

Run:  python tracker.py --source video.mp4 --out tracks.csv --show
Crowded scene:  python tracker.py --source video.mp4 --tiles --show
"""
import argparse, csv, math, os, time, threading, traceback
from collections import deque, Counter
import cv2
import numpy as np
from ultralytics import YOLO

import config as cfg
from geometry import ground_point, heading_deg, direction_name, build_homography, to_meters
from zones_io import load_zones, scale_zones
from tiled import detect_tiled, SimpleTracker
from wrong_side import WrongSideDetector, EVENT_FIELDS
from risk import RiskEngine, RiderFinder, TITLES
from display import set_dpi_aware, ZoomView

CSV_FIELDS = ["frame", "time_s", "track_id", "class", "x", "y", "w", "h",
              "speed_kmh", "heading_deg", "direction"]


class TrackHistory:
    """Keeps recent positions for one object; works out speed, heading and its best label."""
    def __init__(self):
        self.points = deque(maxlen=cfg.HISTORY_LENGTH)      # (time_s, mx, my) in meters or pixels
        self.px = deque(maxlen=cfg.HISTORY_LENGTH)          # (x, y) in pixels, for N/E/S/W
        self.votes = Counter()
        self.last_seen = 0.0

    def add(self, t, mx, my, gx, gy, cls):
        self.points.append((t, mx, my))
        self.px.append((gx, gy))
        self.votes[cls] += 1
        self.last_seen = t

    def best_class(self, current):
        """Most common label so far (or the current one if voting is off)."""
        return self.votes.most_common(1)[0][0] if cfg.LABEL_VOTING else current

    def velocity(self, height=None):
        """Movement in pixels per second over the last VEL_FRAMES frames. With the box height given, movement
        slower than VEL_DEADBAND_H box heights per second counts as standing still (the boxes shake a little)."""
        n = min(cfg.VEL_FRAMES, len(self.px))
        if n < 5:
            return 0.0, 0.0
        dt = self.points[-1][0] - self.points[-n][0]
        if dt <= 0:
            return 0.0, 0.0
        a, b = self.px[-n], self.px[-1]
        vx, vy = (b[0] - a[0]) / dt, (b[1] - a[1]) / dt
        if height and math.hypot(vx, vy) < cfg.VEL_DEADBAND_H * height:
            return 0.0, 0.0
        return vx, vy

    def moved_px(self):
        """How many pixels the object moved over the last 6 frames."""
        if len(self.px) < 6:
            return 0.0
        a, b = self.px[-6], self.px[-1]
        return math.hypot(b[0] - a[0], b[1] - a[1])

    def motion(self, calibrated):
        """Return (speed, heading, direction). Speed is km/h if calibrated, else px/s."""
        if len(self.points) < 6:
            return 0.0, 0.0, "-"
        t0, x0, y0 = self.points[-6]
        t1, x1, y1 = self.points[-1]
        dt = t1 - t0
        if dt <= 0:
            return 0.0, 0.0, "-"
        speed = math.hypot(x1 - x0, y1 - y0) / dt * (3.6 if calibrated else 1.0)
        a, b = self.px[-6], self.px[-1]
        dx, dy = b[0] - a[0], b[1] - a[1]
        ang = heading_deg(dx, dy) if (dx or dy) else 0.0
        return speed, ang, direction_name(ang)


def label_color(cls, event_level=None):
    """Green normally, yellow for warning, red for danger, blue for emergency vehicles."""
    if cls in cfg.EMERGENCY_CLASSES:
        return cfg.BLUE
    return {"warning": cfg.YELLOW, "danger": cfg.RED}.get(event_level, cfg.GREEN)


def draw_object(frame, x1, y1, x2, y2, tag, color):
    """Draw the box and the label bar above it: CLASS #ID | SPEED | DIRECTION."""
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
    (tw, th), _ = cv2.getTextSize(tag, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
    top = max(0, y1 - th - 8)
    cv2.rectangle(frame, (x1, top), (x1 + tw + 8, top + th + 8), color, -1)
    cv2.putText(frame, tag, (x1 + 4, top + th + 2), cv2.FONT_HERSHEY_SIMPLEX, 0.5, cfg.TEXT_DARK, 1, cv2.LINE_AA)


def draw_zones(frame, zones):
    """Semi-transparent purple polygons for restricted zones."""
    import numpy as np
    if not zones.get("restricted_zones"):
        return
    overlay = frame.copy()
    for z in zones["restricted_zones"]:
        pts = np.array(z["polygon"], dtype=np.int32)
        cv2.fillPoly(overlay, [pts], cfg.PURPLE)
        cv2.polylines(frame, [pts], True, cfg.PURPLE, 2)
        cv2.putText(frame, z["name"], tuple(pts[0]), cv2.FONT_HERSHEY_SIMPLEX, 0.5, cfg.PURPLE, 1, cv2.LINE_AA)
    cv2.addWeighted(overlay, 0.25, frame, 0.75, 0, frame)


def in_ignore_zone(ignore_polys, gx, gy):
    """True if this ground point is inside an area we told the system to ignore."""
    return any(cv2.pointPolygonTest(p, (float(gx), float(gy)), False) >= 0 for p in ignore_polys)


def draw_ignore_zones(frame, zones):
    """Thin grey outline around ignore areas, so you can see what is being skipped."""
    import numpy as np
    for z in zones.get("ignore_zones", []):
        pts = np.array(z["polygon"], dtype=np.int32)
        cv2.polylines(frame, [pts], True, (150, 150, 150), 1)
        cv2.putText(frame, "ignored", tuple(pts[0]), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (150, 150, 150), 1, cv2.LINE_AA)


def team_class(model_names, cls_id):
    """Convert a model class name to the exact team class name (or None to skip)."""
    name = model_names[cls_id]
    return name if name in cfg.TEAM_CLASSES else cfg.COCO_TO_TEAM.get(name)


def get_objects(model, frame, tiled, simple_tracker):
    """Return a list of (x1, y1, x2, y2, track_id, class_id, confidence) for this frame."""
    low_conf = min([cfg.CONF_THRESHOLD] + list(cfg.PER_CLASS_CONF.values()))
    if tiled:
        dets = detect_tiled(model, frame, cfg.TILE_COLS, cfg.TILE_ROWS, 0.2, cfg.IMGSZ, low_conf, cfg.IOU)
        return simple_tracker.update(dets)
    r = model.track(frame, persist=True, tracker=cfg.TRACKER, conf=low_conf,
                    imgsz=cfg.IMGSZ, iou=cfg.IOU, verbose=False)[0]
    if r.boxes is None or r.boxes.id is None:
        return []
    return [(*[float(v) for v in b], int(i), int(c), float(s))
            for b, i, c, s in zip(r.boxes.xyxy, r.boxes.id, r.boxes.cls, r.boxes.conf)]


def resolve_model(path):
    """Find the model file as given, or next to this code (so the app finds it from any folder)."""
    if os.path.exists(path):
        return path
    beside = os.path.join(cfg.TRACKING_DIR, path)
    return beside if os.path.exists(beside) else path      # otherwise ultralytics downloads it


class Pipeline:
    """Everything that happens to ONE video frame: detect, track, measure, check rules, draw.
    The command-line tracker and the desktop app both use this class."""

    def __init__(self, model_path, zones_path, fps, frame_size, tiled=False, show_conf=False):
        self.model = YOLO(resolve_model(model_path))
        self.zones = scale_zones(load_zones(zones_path), frame_size[0], frame_size[1])
        self.H = build_homography(self.zones.get("calibration")) if cfg.USE_CALIBRATION else None
        self.detector = WrongSideDetector(self.zones)
        self.risk = RiskEngine(self.zones, fps)
        self.riders = RiderFinder()
        self.ignore_polys = [np.array(z["polygon"], dtype="float32") for z in self.zones.get("ignore_zones", [])]
        self.tiled = tiled
        self.simple_tracker = SimpleTracker(fps=fps) if tiled else None
        self.show_conf = cfg.SHOW_CONF or show_conf
        self.histories = {}
        self.banner, self.banner_until = "", 0.0
        self.seen = {"vehicles": set(), "pedestrians": set()}     # unique track IDs (approximate counts)

    def counts(self):
        """Approximate totals so far: how many different vehicles / pedestrians were tracked."""
        return {"vehicles": len(self.seen["vehicles"]), "pedestrians": len(self.seen["pedestrians"]), "traffic": self.risk.level}

    def zone_name(self, x, y):
        """Name of the road area a point is in (from zones.json), or - if none."""
        area = self.detector.area_of(x, y)
        return area["name"] if area else "-"

    def process(self, frame, frame_no, t):
        """Run one frame. Draws on the frame. Returns (frame, track_records, new_events)."""
        records, events, tracks, to_draw = [], [], [], []
        calibrated = self.H is not None
        draw_zones(frame, self.zones)
        draw_ignore_zones(frame, self.zones)
        for x1, y1, x2, y2, tid, cid, conf in get_objects(self.model, frame, self.tiled, self.simple_tracker):
            cls = team_class(self.model.names, cid)
            if cls is None or conf < cfg.PER_CLASS_CONF.get(cls, cfg.CONF_THRESHOLD):
                continue
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
            gx, gy = ground_point(x1, y1, x2, y2)
            if in_ignore_zone(self.ignore_polys, gx, gy):
                continue                                      # inside an ignore area (for example a mailbox)
            mx, my = to_meters(self.H, gx, gy)
            hist = self.histories.setdefault(tid, TrackHistory())
            hist.add(t, mx, my, gx, gy, cls)
            if len(hist.points) < cfg.MIN_TRACK_FRAMES:
                continue                                      # too new: wait a few frames before trusting it
            cls = hist.best_class(cls)
            self.seen["pedestrians" if cls == "person" else "vehicles"].add(tid)
            speed, ang, dname = hist.motion(calibrated)
            unit = "km/h" if calibrated else "px/s"
            tag = f"{cfg.DISPLAY_NAME[cls]} #{tid} | {speed:.0f} {unit} | {dname}"
            if self.show_conf:
                tag += f" | {conf:.2f}"
            ev = self.detector.update(frame_no, t, tid, cls, gx, gy, ang, hist.moved_px())
            if ev:
                events.append(ev)
                self.banner, self.banner_until = "WRONG SIDE DRIVING - " + ev["objects"], t + 3.0
            vx, vy = hist.velocity(y2 - y1)
            tracks.append({"tid": tid, "cls": cls, "x1": x1, "y1": y1, "x2": x2, "y2": y2, "gx": gx, "gy": gy,
                           "vx": vx, "vy": vy, "speed": math.hypot(vx, vy), "age": len(hist.points)})
            to_draw.append((x1, y1, x2, y2, tag, cls, tid))
            records.append({"frame": frame_no, "time_s": round(t, 2), "track_id": tid, "class": cls,
                            "x": round(gx, 1), "y": round(gy, 1), "w": x2 - x1, "h": y2 - y1,
                            "speed_kmh": round(speed, 1), "heading_deg": round(ang, 1), "direction": dname})
        rider_ids = self.riders.update(tracks)                               # people riding bikes are not pedestrians
        for tid in rider_ids:
            self.seen["pedestrians"].discard(tid)
        for r in records:
            if r["track_id"] in rider_ids and r["class"] == "person":
                r["class"] = "rider"
        to_draw = [(x1, y1, x2, y2, tag.replace("Ped #", "Rider #", 1) if tid in rider_ids else tag, cls, tid)
                   for x1, y1, x2, y2, tag, cls, tid in to_draw]
        tracks = [a for a in tracks if a["tid"] not in rider_ids]            # the bike represents its rider in the risk rules
        for ev in self.risk.update(frame_no, t, tracks, self.zone_name):      # near miss, braking, lane change ...
            events.append(ev)
            if ev["severity"] in ("HIGH", "CRITICAL"):
                self.banner, self.banner_until = f"{TITLES[ev['type']]} - {ev['objects']}", t + 3.0
        for x1, y1, x2, y2, tag, cls, tid in to_draw:                        # boxes: red = danger, yellow = warning
            level = "danger" if self.detector.is_flagged(tid) else self.risk.level_of(tid, t)
            draw_object(frame, x1, y1, x2, y2, tag, label_color(cls, level))
        if self.banner and t < self.banner_until:             # red alert bar at the top of the video
            cv2.rectangle(frame, (0, 0), (frame.shape[1], 34), cfg.RED, -1)
            cv2.putText(frame, self.banner, (12, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
        for k in [k for k, h in self.histories.items() if t - h.last_seen > cfg.MAX_MISSING_SECONDS]:
            del self.histories[k]
        return frame, records, events


class FrameSlot:
    """Hands the newest finished picture from the AI thread to the window."""
    def __init__(self):
        self.lock = threading.Lock()
        self.frame, self.done, self.stop, self.error = None, False, False, None

    def put(self, frame):
        with self.lock:
            self.frame = frame

    def get(self):
        with self.lock:
            return self.frame


def run(source, out_csv, zones_path, model_path, show, tiled, events_csv="events.csv", show_conf_flag=False):
    set_dpi_aware()
    cap = cv2.VideoCapture(0 if source == "webcam" else source)
    if not cap.isOpened():
        print(f"Could not open the video: {source}")
        return
    vw, vh = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    is_file = source != "webcam" and not str(source).startswith("rtsp")
    pipe = Pipeline(model_path, zones_path, fps, (vw, vh), tiled, show_conf_flag)
    if tiled:
        print("Tiled mode ON: slower, but finds small and far vehicles.")

    viewer = ZoomView("Urban Road Safety AI - Tracking", *cfg.DISPLAY_MAX) if show else None
    slot = FrameSlot()
    result = {"frames": 0}

    def work():
        """Read video, run the pipeline, write files. Runs in the background when showing video."""
        frame_no, t_start = 0, time.time()
        with open(out_csv, "w", newline="") as f, open(events_csv, "w", newline="") as ef:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writeheader()
            ev_writer = csv.DictWriter(ef, fieldnames=EVENT_FIELDS)
            ev_writer.writeheader()
            while not slot.stop:
                ok, frame = cap.read()
                if not ok:
                    break
                t = frame_no / fps if is_file else time.time() - t_start   # video time in seconds
                frame, records, events = pipe.process(frame, frame_no, t)
                writer.writerows(records)
                for ev in events:
                    ev_writer.writerow(ev)
                    print(f"[{ev['type']}] [{ev['severity']}] {ev['objects']} | {ev['zone']} | {ev['time']} | {ev['details']}")
                if viewer:
                    slot.put(frame)                          # the window shows it; we never touch it again
                    while viewer.paused and not viewer.step and not slot.stop:
                        time.sleep(0.01)                     # paused: wait (N = one frame forward)
                    viewer.step = False
                frame_no += 1
        result["frames"] = frame_no

    def work_safely():
        try:
            work()
        except Exception:
            slot.error = traceback.format_exc()
        slot.done = True

    if viewer:
        thread = threading.Thread(target=work_safely, daemon=True)
        thread.start()
        told = False
        while True:
            frame = slot.get()
            if frame is None:
                if slot.done:
                    break
                cv2.waitKey(10)
                continue
            if not viewer.tick(frame):
                break
            if slot.done and not told:
                told = True
                print("Video finished. You can keep zooming. Press Q in the window to close.")
            if slot.error:
                break
        slot.stop = True
        thread.join()
        if slot.error:
            print(slot.error)
    else:
        work()
    cap.release()
    cv2.destroyAllWindows()
    print(f"Done. {result['frames']} frames. Track records saved to {out_csv}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, help="video file, 'webcam', or rtsp:// link")
    ap.add_argument("--out", default="tracks.csv")
    ap.add_argument("--zones", default="zones.json")
    ap.add_argument("--events", default="events.csv", help="where wrong-side events are saved")
    ap.add_argument("--model", default=cfg.MODEL_PATH)
    ap.add_argument("--show", action="store_true", help="show the video window")
    ap.add_argument("--show-conf", action="store_true", help="show the AI confidence on each label")
    ap.add_argument("--tiles", action="store_true", help="crowded scenes: find small/far vehicles (slower)")
    a = ap.parse_args()
    run(a.source, a.out, a.zones, a.model, a.show, a.tiles or cfg.TILED, a.events, a.show_conf)
