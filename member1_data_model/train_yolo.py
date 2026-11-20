"""Fine-tune YOLO. Works on Google Colab (free GPU) or a local GPU.

Compare the two models:
  python member1_data_model/train_yolo.py --model yolov8s.pt --name v8s
  python member1_data_model/train_yolo.py --model yolo11s.pt --name y11s
Best weights are copied to models/best_<name>.pt . Copy the winner to models/best.pt
"""
import argparse
import shutil
from pathlib import Path

from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[1]

ap = argparse.ArgumentParser()
ap.add_argument("--model", default="yolov8s.pt")
ap.add_argument("--name", default="run1")
ap.add_argument("--data", default=str(ROOT / "dataset_test" / "data.yaml"))
ap.add_argument("--epochs", type=int, default=50)
ap.add_argument("--imgsz", type=int, default=640)
ap.add_argument("--batch", type=int, default=16)
a = ap.parse_args()

model = YOLO(a.model)
model.train(data=a.data, epochs=a.epochs, imgsz=a.imgsz, batch=a.batch,
            project=str(ROOT / "runs"), name=a.name, patience=15, plots=True)

best = ROOT / "runs" / a.name / "weights" / "best.pt"
dst = ROOT / "models" / f"best_{a.name}.pt"
shutil.copy(best, dst)
print("Saved", dst)

