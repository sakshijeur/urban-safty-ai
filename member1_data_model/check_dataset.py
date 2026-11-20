"""Count labelled boxes per class and per split. Warns when a class has < 300 boxes.
Run:  python member1_data_model/check_dataset.py
"""
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
NAMES = yaml.safe_load((ROOT / "config" / "classes.yaml").read_text())["names"]
LABELS = ROOT / "dataset_test" / "labels"

total = Counter()
for split in ("train", "val", "test"):
    c = Counter()
    for f in (LABELS / split).glob("*.txt"):
        for ln in f.read_text().splitlines():
            if ln.strip():
                c[NAMES[int(ln.split()[0])]] += 1
    total += c
    print(f"{split:5s}", dict(c))
print("\nTOTAL per class")
for n in NAMES:
    flag = "  <-- add more images" if total[n] < 300 else ""
    print(f"  {n:11s} {total[n]:6d}{flag}")

