"""Draw an area on your own video and save it to zones.json.

Restricted zone (purple, for entry alerts):   python draw_zone.py --source test.mp4
Ignore area (grey, detections inside are skipped, for example a mailbox or a sign):
                                              python draw_zone.py --source test.mp4 --kind ignore

Mouse / keys:
  Left click  = add a corner point (click around the area, in order)
  ENTER       = finish this area and save it
  U           = undo last point
  C           = clear all saved areas of this kind
  Q           = quit
"""
import argparse
import cv2
import numpy as np
import config as cfg
from display import set_dpi_aware
from zones_io import load_zones, save_zones

points = []
KINDS = {"restricted": ("restricted_zones", "Restricted Zone", cfg.PURPLE),
         "ignore": ("ignore_zones", "Ignore Area", (150, 150, 150))}


def on_mouse(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        points.append((x, y))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--zones", default="zones.json")
    ap.add_argument("--kind", choices=list(KINDS), default="restricted")
    a = ap.parse_args()
    key_name, label, color = KINDS[a.kind]

    set_dpi_aware()
    cap = cv2.VideoCapture(a.source)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        print("Could not read the video.")
        return
    h, w = frame.shape[:2]
    scale = min(1.0, 1280 / w, 720 / h)          # shrink big videos to fit the screen
    shown = cv2.resize(frame, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

    zones = load_zones(a.zones)
    zones["frame_size"] = [w, h]
    zones.setdefault(key_name, [])
    win = f"Draw {a.kind} area: click corners, ENTER=save, U=undo, C=clear, Q=quit"
    cv2.namedWindow(win)
    cv2.setMouseCallback(win, on_mouse)

    while True:
        view = shown.copy()
        for name, (kn, lab, col) in KINDS.items():           # show saved areas of both kinds
            for z in zones.get(kn, []):
                pts = (np.array(z["polygon"]) * scale).astype(np.int32)
                cv2.polylines(view, [pts], True, col, 2)
                cv2.putText(view, z["name"], tuple(pts[0]), cv2.FONT_HERSHEY_SIMPLEX, 0.5, col, 1)
        for p in points:
            cv2.circle(view, p, 4, cfg.YELLOW, -1)
        if len(points) > 1:
            cv2.polylines(view, [np.array(points, dtype=np.int32)], False, cfg.YELLOW, 2)
        cv2.imshow(win, view)
        k = cv2.waitKey(20) & 0xFF
        if k in (ord("q"), ord("Q")):
            break
        if k in (ord("u"), ord("U")) and points:
            points.pop()
        if k in (ord("c"), ord("C")):
            zones[key_name] = []
            save_zones(a.zones, zones)
            print(f"Cleared all {a.kind} areas.")
        if k == 13 and len(points) >= 3:             # ENTER
            n = len(zones[key_name]) + 1
            zones[key_name].append({
                "id": f"{a.kind[0].upper()}{n}", "name": f"{label} {n:02d}", "type": a.kind,
                "polygon": [[round(x / scale), round(y / scale)] for x, y in points]})
            save_zones(a.zones, zones)
            print(f"Saved {label} {n:02d} to {a.zones}")
            points.clear()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
