"""Runs the video analysis in the background so the app window never freezes.

It uses the same Pipeline as the command-line tracker (tracking/tracker.py)."""
import os
import time
import traceback
import cv2
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage


def to_qimage(bgr):
    """OpenCV picture (BGR) -> Qt picture."""
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    h, w, ch = rgb.shape
    return QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888).copy()


class AnalysisWorker(QThread):
    frame_ready = Signal(QImage)     # a finished picture with boxes and labels
    events_found = Signal(list)      # new safety events
    stats = Signal(dict)             # vehicles, pedestrians, frame, total, fps
    status = Signal(str)             # a message for the status line
    summary = Signal(dict)           # frames, duration, totals and the per-object summary (saved to the database)
    finished_ok = Signal()
    failed = Signal(str)

    def __init__(self, source, tiled=False, model_path=None, snap_dir=None, session_id=0):
        super().__init__()
        self.source, self.tiled, self.model_path = source, tiled, model_path
        self.snap_dir, self.session_id = snap_dir, session_id
        self.paused = self.stop_flag = self.step = False

    def save_snapshot(self, frame, frame_no):
        """Save the picture (with boxes) at the moment of an event. Returns its short relative path."""
        scale = min(1.0, 720 / frame.shape[1])
        small = cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1 else frame
        name = f"snapshots/s{self.session_id}_f{frame_no}.jpg"
        cv2.imwrite(os.path.join(os.path.dirname(self.snap_dir), name), small, [cv2.IMWRITE_JPEG_QUALITY, 80])
        return name

    def stop(self):
        self.stop_flag = True
        self.wait(5000)

    def run(self):
        cap = None
        try:
            import config as cfg          # these live in the tracking folder (added to the path in main.py)
            import tracker
        except ImportError as e:
            self.failed.emit(f"A library is missing: {e}. Run:  pip install -r ../tracking/requirements.txt")
            return
        try:
            self.status.emit("Opening video...")
            is_file = self.source != "webcam"
            cap = cv2.VideoCapture(0 if not is_file else self.source)
            if not cap.isOpened():
                self.failed.emit("Could not open the video or camera.")
                return
            w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) if is_file else 0
            self.status.emit("Loading the AI model (the first time can take a minute)...")
            zones_path = os.path.join(cfg.TRACKING_DIR, "zones.json")
            pipe = tracker.Pipeline(self.model_path or cfg.MODEL_PATH, zones_path, fps, (w, h), self.tiled)
            frame_no, t_start = 0, time.time()
            agg = {}                                   # track id -> [class, first frame, last frame, speed sum, count, max speed]
            win_start, win_frames = time.time(), 0
            while not self.stop_flag:
                ok, frame = cap.read()
                if not ok:
                    break
                t = frame_no / fps if is_file else time.time() - t_start
                frame, records, events = pipe.process(frame, frame_no, t)
                for r in records:
                    a = agg.setdefault(r["track_id"], [r["class"], r["frame"], r["frame"], 0.0, 0, 0.0])
                    a[2], a[3], a[4], a[5] = r["frame"], a[3] + r["speed_kmh"], a[4] + 1, max(a[5], r["speed_kmh"])
                self.frame_ready.emit(to_qimage(frame))
                if events:
                    name = self.save_snapshot(frame, frame_no) if self.snap_dir else None
                    for ev in events:
                        ev["snapshot"] = name
                    self.events_found.emit(events)
                frame_no += 1
                win_frames += 1
                now = time.time()
                if now - win_start >= 0.5:
                    self.stats.emit({**pipe.counts(), "frame": frame_no, "total": total, "fps": win_frames / (now - win_start)})
                    win_start, win_frames = now, 0
                if self.paused:
                    while self.paused and not self.stop_flag and not self.step:
                        self.msleep(20)
                    win_start, win_frames = time.time(), 0       # do not count paused time in the speed
                self.step = False
            self.stats.emit({**pipe.counts(), "frame": frame_no, "total": total, "fps": 0.0})
            self.summary.emit({"frames": frame_no, "duration_s": frame_no / fps, **{k: v for k, v in pipe.counts().items() if k != "traffic"},
                               "tracks": [(tid, a[0], a[1], a[2], round(a[3] / max(a[4], 1), 1), round(a[5], 1)) for tid, a in agg.items()]})
            self.finished_ok.emit()
        except Exception:
            self.failed.emit(traceback.format_exc())
        finally:
            if cap is not None:
                cap.release()
