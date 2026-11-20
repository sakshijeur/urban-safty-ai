# Member 1 - Data & Model

**Goal:** a model that recognises all 9 classes (car, bike, bus, truck, auto, ambulance,
fire_truck, police, person) and a good set of test videos.

| Handbook task | Script / file |
|---|---|
| Collect clips, note source + license | `sources.txt` |
| Cut long videos, sort into folders | `split_videos.py` |
| Merge datasets, exact class names, 80/10/10 | `prepare_dataset.py` |
| Check images/boxes per class | `check_dataset.py` |
| Train yolov8s vs yolo11s (Colab) | `train_yolo.py` |
| mAP50 per class table | `evaluate_model.py` |
| Flashing red/blue light second signal | `emergency_light_check.py` |

Deliverables: `models/best.pt`, `dataset/data.yaml` + this README (describe your dataset below),
`videos/`, accuracy table in `docs/`.

## Week plan
1. Collect clips, choose datasets  2. Label, merge, first training  3. Better model + accuracy table
4. Check false detections, retrain  5. Final model, demo videos, help with report

## Dataset description (fill in)
- Sources used: ...
- Images per split: train ... / val ... / test ...
- Boxes per class: ...
- Night/rain images added: ...

## Finished when
The model finds all 9 classes on the test clips with acceptable accuracy and the dataset is documented.
