"""Cut a long video into short clips and save them in videos/<category>/.

Example:
  python member1_data_model/split_videos.py --input long_cctv.mp4 --category crowded --seconds 30
"""
import argparse
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
CATEGORIES = ["normal", "crowded", "pedestrians", "wrong_side", "braking",
              "lane_change", "emergency", "night_rain", "accident"]


def split_video(path: Path, out_dir: Path, seconds: int, prefix: str) -> int:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise SystemExit(f"Cannot open {path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    w, h = int(cap.get(3)), int(cap.get(4))
    per_clip = int(fps * seconds)
    out_dir.mkdir(parents=True, exist_ok=True)
    clip_no, frame_no, writer = 0, 0, None
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if frame_no % per_clip == 0:
            if writer:
                writer.release()
            clip_no += 1
            name = out_dir / f"{prefix}_{clip_no:03d}.mp4"
            writer = cv2.VideoWriter(str(name), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
        writer.write(frame)
        frame_no += 1
    if writer:
        writer.release()
    cap.release()
    return clip_no


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--category", required=True, choices=CATEGORIES)
    ap.add_argument("--seconds", type=int, default=30)
    a = ap.parse_args()
    src = Path(a.input)
    n = split_video(src, ROOT / "videos" / a.category, a.seconds, src.stem)
    print(f"Saved {n} clips in videos/{a.category}/  -> now add them to member1_data_model/sources.txt")
