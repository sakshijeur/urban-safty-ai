"""Tiled detection + a simple tracker, for crowded scenes with small, far vehicles.

Each frame is cut into overlapping tiles. Every tile is shown to the AI at full detail,
so small vehicles become big enough to be found. Results are merged into one list.
"""
import numpy as np
import cv2


def _iou(a, b):
    """Overlap between two boxes (x1,y1,x2,y2), from 0 to 1."""
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def detect_tiled(model, frame, cols=2, rows=2, overlap=0.2, imgsz=960, conf=0.2, iou=0.5, merge_iou=0.55):
    """Return an array of detections: [x1, y1, x2, y2, confidence, class_id]."""
    h, w = frame.shape[:2]
    tw, th = w / (cols - (cols - 1) * overlap), h / (rows - (rows - 1) * overlap)
    sx, sy = tw * (1 - overlap), th * (1 - overlap)
    windows = [(0, 0, w, h)]  # the whole frame too, so big vehicles are not cut in half
    for r in range(rows):
        for c in range(cols):
            x0, y0 = int(c * sx), int(r * sy)
            windows.append((x0, y0, min(w, int(x0 + tw)), min(h, int(y0 + th))))

    found = []
    for (x0, y0, x1, y1) in windows:
        crop = frame[y0:y1, x0:x1]
        res = model.predict(crop, imgsz=imgsz, conf=conf, iou=iou, verbose=False)[0]
        if res.boxes is None or len(res.boxes) == 0:
            continue
        xyxy = res.boxes.xyxy.cpu().numpy()
        cf = res.boxes.conf.cpu().numpy()
        cl = res.boxes.cls.cpu().numpy()
        for b, s, k in zip(xyxy, cf, cl):
            bw, bh = b[2] - b[0], b[3] - b[1]
            touches_edge = (b[0] <= 2 and x0 > 0) or (b[1] <= 2 and y0 > 0) or \
                           (b[2] >= (x1 - x0) - 2 and x1 < w) or (b[3] >= (y1 - y0) - 2 and y1 < h)
            if touches_edge and (x1 - x0, y1 - y0) != (w, h):
                continue  # box cut by a tile edge; the neighbouring tile will see it whole
            found.append([b[0] + x0, b[1] + y0, b[2] + x0, b[3] + y0, float(s), int(k)])

    # merge duplicates from overlapping tiles (keep the most confident one)
    found.sort(key=lambda d: -d[4])
    kept = []
    for d in found:
        if all(_iou(d, k) < merge_iou for k in kept):
            kept.append(d)
    return np.array(kept, dtype=np.float32).reshape(-1, 6)


class SimpleTracker:
    """Light tracker: matches new boxes to old tracks by overlap and predicted position."""

    def __init__(self, fps=25.0, max_missing_s=1.0, match_iou=0.2, min_hits=2):
        self.max_missing = max(1, int(fps * max_missing_s))
        self.match_iou, self.min_hits = match_iou, min_hits
        self.tracks, self.next_id = [], 1

    def update(self, dets):
        """dets: Nx6 array. Returns list of (x1,y1,x2,y2,track_id,class_id,conf) for confirmed tracks."""
        for t in self.tracks:  # predict where each track should be now
            t["pred"] = [t["box"][i] + t["vel"][i % 2] for i in range(4)]
        pairs = []
        for ti, t in enumerate(self.tracks):
            for di, d in enumerate(dets):
                v = _iou(t["pred"], d[:4])
                if v >= self.match_iou:
                    pairs.append((v, ti, di))
        pairs.sort(reverse=True)
        used_t, used_d = set(), set()
        for v, ti, di in pairs:
            if ti in used_t or di in used_d:
                continue
            t, d = self.tracks[ti], dets[di]
            old = t["box"]
            nb = [float(x) for x in d[:4]]
            t["vel"] = [0.5 * t["vel"][0] + 0.5 * ((nb[0] + nb[2]) / 2 - (old[0] + old[2]) / 2),
                        0.5 * t["vel"][1] + 0.5 * ((nb[1] + nb[3]) / 2 - (old[1] + old[3]) / 2)]
            t["box"], t["conf"], t["missing"] = nb, float(d[4]), 0
            t["hits"] += 1
            t["cls"] = int(d[5])
            used_t.add(ti); used_d.add(di)
        for ti, t in enumerate(self.tracks):
            if ti not in used_t:
                t["missing"] += 1
        for di, d in enumerate(dets):
            if di not in used_d:
                self.tracks.append({"id": self.next_id, "box": [float(x) for x in d[:4]], "vel": [0.0, 0.0],
                                    "pred": None, "conf": float(d[4]), "cls": int(d[5]), "hits": 1, "missing": 0})
                self.next_id += 1
        self.tracks = [t for t in self.tracks if t["missing"] <= self.max_missing]
        return [(*t["box"], t["id"], t["cls"], t["conf"]) for t in self.tracks
                if t["missing"] == 0 and t["hits"] >= self.min_hits]
