"""Second signal for emergency vehicles: flashing red/blue lights.

Use as a function (frame crop -> ratios) or run on a video:
  python member1_data_model/emergency_light_check.py --video videos/emergency/clip.mp4
"""
import argparse
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def red_blue_ratio(crop_bgr):
    """Fraction of bright, saturated RED and BLUE pixels in the top 40% of a vehicle box
    (light bars are on the roof)."""
    h = crop_bgr.shape[0]
    roof = crop_bgr[: max(1, int(h * 0.4))]
    hsv = cv2.cvtColor(roof, cv2.COLOR_BGR2HSV)
    bright = (hsv[..., 1] > 120) & (hsv[..., 2] > 180)
    red = bright & ((hsv[..., 0] < 10) | (hsv[..., 0] > 170))
    blue = bright & (hsv[..., 0] > 100) & (hsv[..., 0] < 130)
    n = roof.shape[0] * roof.shape[1]
    return red.sum() / n, blue.sum() / n


def is_flashing(history, min_ratio=0.01, min_change=0.005):
    """history = list of (red_ratio, blue_ratio) for one track over recent frames.
    True when BOTH colours appear and their values change over time (flashing)."""
    if len(history) < 10:
        return False
    r = np.array([h[0] for h in history])
    b = np.array([h[1] for h in history])
    both = r.max() > min_ratio and b.max() > min_ratio
    changing = r.std() > min_change or b.std() > min_change
    return bool(both and changing)


if __name__ == "__main__":
    from ultralytics import YOLO

    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--model", default=str(ROOT / "models" / "best.pt"))
    a = ap.parse_args()
    model = YOLO(a.model)
    hist, flagged = defaultdict(list), set()
    for res in model.track(a.video, stream=True, persist=True, tracker="bytetrack.yaml", verbose=False):
        frame = res.orig_img
        if res.boxes.id is None:
            continue
        for box, tid in zip(res.boxes.xyxy.int().tolist(), res.boxes.id.int().tolist()):
            x1, y1, x2, y2 = box
            crop = frame[max(0, y1):y2, max(0, x1):x2]
            if crop.size == 0:
                continue
            hist[tid].append(red_blue_ratio(crop))
            hist[tid] = hist[tid][-30:]
            if tid not in flagged and is_flashing(hist[tid]):
                flagged.add(tid)
                print(f"Track #{tid}: flashing red/blue lights detected -> emergency vehicle")
    print("Flashing tracks:", sorted(flagged) or "none")
