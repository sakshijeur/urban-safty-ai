"""Tell the system which way traffic should flow, for wrong-side detection.

Run:  python draw_direction.py --source test.mp4

For each road side (carriageway):
  1. Left-click 3 or more corners around the road area, then press ENTER.
  2. Click TWO points for the arrow: START, then END (the way cars SHOULD travel).
Repeat for the other side of the road. Both sides need their own arrow, pointing opposite ways.

Keys: U = undo point, C = clear all saved areas, Q = quit
"""
import argparse
import cv2
from display import set_dpi_aware
import numpy as np
import config as cfg
from geometry import heading_deg, direction_name
from zones_io import load_zones, save_zones

state = {"clicks": [], "poly": None}


def on_mouse(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        state["clicks"].append((x, y))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--zones", default="zones.json")
    a = ap.parse_args()
    set_dpi_aware()
    cap = cv2.VideoCapture(a.source)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        print("Could not read the video.")
        return
    h, w = frame.shape[:2]
    scale = min(1.0, 1280 / w, 720 / h)
    shown = cv2.resize(frame, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    zones = load_zones(a.zones)
    zones["frame_size"] = [w, h]
    win = "Direction: corners then ENTER, then 2 clicks for the arrow (start, end) | U=undo C=clear Q=quit"
    cv2.namedWindow(win)
    cv2.setMouseCallback(win, on_mouse)

    while True:
        view = shown.copy()
        for r in zones.get("road_directions", []):
            pts = (np.array(r["polygon"]) * scale).astype(np.int32)
            cv2.polylines(view, [pts], True, cfg.GREEN, 2)
            c = pts.mean(axis=0).astype(int)
            v = np.array(r["expected_vector"], dtype=float)
            tip = (int(c[0] + v[0] * 60), int(c[1] + v[1] * 60))
            cv2.arrowedLine(view, (int(c[0]), int(c[1])), tip, cfg.GREEN, 3, tipLength=0.3)
            cv2.putText(view, f'{r["zone"]}: {r.get("label", "")}', (int(pts[0][0]), int(pts[0][1]) - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, cfg.GREEN, 2)
        clicks = state["clicks"]
        if state["poly"] is None:
            for p in clicks:
                cv2.circle(view, p, 4, cfg.YELLOW, -1)
            if len(clicks) > 1:
                cv2.polylines(view, [np.array(clicks, dtype=np.int32)], False, cfg.YELLOW, 2)
            msg = "Click corners around one side of the road, then ENTER"
        else:
            cv2.polylines(view, [np.array(state["poly"], dtype=np.int32)], True, cfg.YELLOW, 2)
            if len(clicks) == 1:
                cv2.circle(view, clicks[0], 5, cfg.BLUE, -1)
            msg = "Click the arrow START, then END (the direction cars SHOULD go)"
        cv2.putText(view, msg, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, cfg.YELLOW, 2)
        cv2.imshow(win, view)

        k = cv2.waitKey(20) & 0xFF
        if k in (ord("q"), ord("Q")):
            break
        if k in (ord("u"), ord("U")) and clicks:
            clicks.pop()
        if k in (ord("c"), ord("C")):
            zones["road_directions"] = []
            save_zones(a.zones, zones)
            print("Cleared all road directions.")
        if k == 13 and state["poly"] is None and len(clicks) >= 3:
            state["poly"] = list(clicks)
            clicks.clear()
        if state["poly"] is not None and len(clicks) == 2:
            (x0, y0), (x1, y1) = clicks
            dx, dy = x1 - x0, y1 - y0
            n = np.hypot(dx, dy)
            if n < 10:
                print("Arrow too short, try again.")
                clicks.clear()
                continue
            ang = heading_deg(dx, dy)
            idx = len(zones.setdefault("road_directions", []))
            zones["road_directions"].append({
                "zone": f"Zone {chr(65 + idx)}",
                "polygon": [[round(x / scale), round(y / scale)] for x, y in state["poly"]],
                "expected_vector": [round(dx / n, 3), round(dy / n, 3)],
                "label": direction_name(ang)})
            save_zones(a.zones, zones)
            print(f"Saved Zone {chr(65 + idx)}: traffic should go {direction_name(ang)}")
            state["poly"] = None
            clicks.clear()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
