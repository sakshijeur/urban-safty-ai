"""Accuracy table (precision, recall, mAP50 per class) on the TEST split.
Run:  python member1_data_model/evaluate_model.py --model models/best_v8s.pt
Creates docs/accuracy_table_<model>.md and .csv  (paste into the report).
"""
import argparse
import csv
from pathlib import Path

from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser()
ap.add_argument("--model", default=str(ROOT / "models" / "best.pt"))
ap.add_argument("--data", default=str(ROOT / "dataset" / "data.yaml"))
a = ap.parse_args()

model = YOLO(a.model)
m = model.val(data=a.data, split="test", verbose=False)
rows = []
for i, cls_id in enumerate(m.box.ap_class_index):
    rows.append([model.names[int(cls_id)], round(float(m.box.p[i]), 3),
                 round(float(m.box.r[i]), 3), round(float(m.box.ap50[i]), 3)])
rows.append(["ALL", round(float(m.box.mp), 3), round(float(m.box.mr), 3), round(float(m.box.map50), 3)])

tag = Path(a.model).stem
out = ROOT / "docs"
out.mkdir(exist_ok=True)
with open(out / f"accuracy_table_{tag}.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["class", "precision", "recall", "mAP50"])
    w.writerows(rows)
with open(out / f"accuracy_table_{tag}.md", "w") as f:
    f.write("| Class | Precision | Recall | mAP50 |\n|---|---|---|---|\n")
    for r in rows:
        f.write(f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} |\n")
print((out / f"accuracy_table_{tag}.md").read_text())
print("If ambulance recall is low -> add more varied images (night/rain), then retrain.")
