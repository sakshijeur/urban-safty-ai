
"""
Merge YOLO datasets into one dataset using the team's class names.

Supports YOLO detection boxes and segmentation polygons.
Output: dataset_test/
"""

import argparse
import random
import shutil
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]

MASTER = yaml.safe_load(
    (ROOT / "config" / "classes.yaml").read_text(encoding="utf-8")
)["names"]


ALIASES = {
    "car": "car", "cars": "car", "sedan": "car",
    "suv": "car", "van": "car", "vehicle": "car",
    "bike": "bike", "motorcycle": "bike", "motorbike": "bike",
    "motorcyclist": "bike", "two-wheeler": "bike",
    "two_wheeler": "bike", "scooter": "bike", "bicycle": "bike",
    "bus": "bus",
    "truck": "truck", "lorry": "truck",
    "auto": "auto", "auto-rickshaw": "auto",
    "autorickshaw": "auto", "auto_rickshaw": "auto",
    "rickshaw": "auto", "rickshaw123": "auto",
    "tuk-tuk": "auto", "tuktuk": "auto", "three-wheeler": "auto",
    "ambulance": "ambulance", "p-ambulance": "ambulance",
    "fire_truck": "fire_truck", "fire truck": "fire_truck",
    "firetruck": "fire_truck", "fire-truck": "fire_truck",
    "fire engine": "fire_truck", "fire_engine": "fire_truck",
    "police": "police", "police car": "police",
    "police_car": "police", "police vehicle": "police",
    "police-vehicle": "police",
    "person": "person", "pedestrian": "person",
    "people": "person", "human": "person",
}


# Manually checked source class IDs -> master class names.
DATASET_ID_MAPS = {
    "ambulance": {
        0: "car",
        1: "ambulance",
    },
    "fire_truck": {
        0: "ambulance",
        1: "fire_truck",
        2: "car",
    },
    "road_vehicles": {
        0: "car",
        1: "bike",
        2: "truck",
        3: "bus",
        4: "ambulance",
        5: "truck",
        6: "auto",
        # ID 7 = tractor; excluded.
    },
}


IMG_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def read_names(ds: Path):
    """Read class names from a dataset's data.yaml."""
    cfg = yaml.safe_load(
        (ds / "data.yaml").read_text(encoding="utf-8")
    )
    names = cfg["names"]

    if isinstance(names, dict):
        return [names[k] for k in sorted(names, key=lambda x: int(x))]

    return list(names)


def collect(ds: Path):
    """Find images and matching YOLO label files."""
    for img in ds.rglob("*"):
        if img.suffix.lower() not in IMG_EXT:
            continue

        parts = list(img.parts)

        if "images" not in parts:
            continue

        i = len(parts) - 1 - parts[::-1].index("images")
        parts[i] = "labels"
        lbl = Path(*parts).with_suffix(".txt")

        if lbl.exists():
            yield img, lbl


def make_id_map(ds: Path, names, skipped):
    """Build source-ID to master-ID mapping."""
    dataset_name = ds.name.lower()

    if dataset_name in DATASET_ID_MAPS:
        return {
            raw_id: MASTER.index(class_name)
            for raw_id, class_name
            in DATASET_ID_MAPS[dataset_name].items()
        }

    idmap = {}

    for i, name in enumerate(names):
        target = ALIASES.get(str(name).strip().lower())

        if target is not None:
            idmap[i] = MASTER.index(target)
        else:
            skipped[f"{ds.name}:{name}"] = 0

    return idmap


def convert_label_line(line, idmap, names, ds_name, skipped, counts):
    """Convert one YOLO box or polygon to a normalized YOLO box."""
    parts = line.split()

    if len(parts) < 5:
        return None

    try:
        cid = int(float(parts[0]))
        coords = [float(v) for v in parts[1:]]
    except ValueError:
        return None

    if cid not in idmap:
        label_name = (
            names[cid] if 0 <= cid < len(names)
            else f"unknown_class_id_{cid}"
        )
        key = f"{ds_name}:{label_name}"
        skipped[key] = skipped.get(key, 0) + 1
        return None

    if len(coords) == 4:
        # YOLO detection box: xc, yc, width, height.
        xc, yc, width, height = coords

    elif len(coords) >= 6 and len(coords) % 2 == 0:
        # Polygon: x1, y1, x2, y2, ...
        xs = coords[0::2]
        ys = coords[1::2]

        xmin, xmax = min(xs), max(xs)
        ymin, ymax = min(ys), max(ys)

        xc = (xmin + xmax) / 2
        yc = (ymin + ymax) / 2
        width = xmax - xmin
        height = ymax - ymin

    else:
        return None

    # Check normalized coordinates.
    if not all(0 <= v <= 1 for v in (xc, yc, width, height)):
        return None

    if width <= 0 or height <= 0:
        return None

    master_id = idmap[cid]
    counts[MASTER[master_id]] += 1

    return (
        f"{master_id} {xc:.8f} {yc:.8f} "
        f"{width:.8f} {height:.8f}"
    )


def main(args):
    raw = Path(args.src)
    out = Path(args.out)

    if not raw.exists():
        raise SystemExit(f"Dataset source folder not found: {raw}")

    datasets = sorted(
        p for p in raw.iterdir()
        if p.is_dir() and (p / "data.yaml").exists()
    )

    if not datasets:
        raise SystemExit(
            f"No dataset folders containing data.yaml found in: {raw}"
        )

    items = []
    skipped = {}
    counts = {name: 0 for name in MASTER}

    for ds in datasets:
        names = read_names(ds)
        idmap = make_id_map(ds, names, skipped)

        print(f"\nReading dataset: {ds.name}")
        print("Class ID mapping:", {
            raw_id: MASTER[master_id]
            for raw_id, master_id in idmap.items()
        })

        for img, lbl in collect(ds):
            converted_lines = []

            for line in lbl.read_text(encoding="utf-8").splitlines():
                converted = convert_label_line(
                    line, idmap, names, ds.name, skipped, counts
                )

                if converted is not None:
                    converted_lines.append(converted)

            if converted_lines:
                items.append((ds.name, img, converted_lines))

    if not items:
        raise SystemExit(
            "No labelled images found. Check images/ and labels/ folders."
        )

    # Deterministic shuffle and 80/10/10 split.
    random.Random(42).shuffle(items)

    total = len(items)
    cut1 = int(total * 0.8)
    cut2 = int(total * 0.9)

    splits = {
        "train": items[:cut1],
        "val": items[cut1:cut2],
        "test": items[cut2:],
    }

    # Only the selected output directory is deleted.
    if out.exists():
        shutil.rmtree(out)

    for split_name, rows in splits.items():
        image_dir = out / "images" / split_name
        label_dir = out / "labels" / split_name

        image_dir.mkdir(parents=True, exist_ok=True)
        label_dir.mkdir(parents=True, exist_ok=True)

        for index, (dataset_name, img, lines) in enumerate(rows):
            stem = f"{dataset_name}_{index:05d}"

            shutil.copy2(
                img,
                image_dir / f"{stem}{img.suffix.lower()}"
            )

            (label_dir / f"{stem}.txt").write_text(
                "\n".join(lines) + "\n",
                encoding="utf-8"
            )

    data = {
        "path": str(out.resolve()),
        "train": "images/train",
        "val": "images/val",
        "test": "images/test",
        "nc": len(MASTER),
        "names": {i: name for i, name in enumerate(MASTER)},
    }

    (out / "data.yaml").write_text(
        yaml.safe_dump(data, sort_keys=False),
        encoding="utf-8"
    )

    print("\n========== DATASET SUMMARY ==========")
    print(f"Total images: {total}")
    print(f"Train images: {len(splits['train'])}")
    print(f"Validation images: {len(splits['val'])}")
    print(f"Test images: {len(splits['test'])}")
    print("\nInstances per master class:")

    for class_name, count in counts.items():
        print(f"  {class_name}: {count}")

    if skipped:
        print("\nSkipped class names / annotations:")
        for name, count in sorted(skipped.items()):
            print(f"  {name}: {count}")

    print(f"\nDone! Dataset created at: {out.resolve()}")
    print(f"YOLO config: {out.resolve() / 'data.yaml'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--src",
        default=str(ROOT / "datasets_raw")
    )

    parser.add_argument(
        "--out",
        default=str(ROOT / "dataset_test")
    )

    main(parser.parse_args())
