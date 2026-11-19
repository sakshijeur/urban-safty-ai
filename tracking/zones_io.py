"""Read and write zones.json (format agreed by Member 2 and Member 4)."""
import json

def load_zones(path):
    """Load zones.json. Returns an empty zone set if the file is missing."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"camera": "", "restricted_zones": [], "lane_lines": [], "road_directions": [],
                "congestion_zones": [], "calibration": None}

def save_zones(path, zones):
    """Save zones to disk (used by the Zone Setup screen)."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(zones, f, indent=2)

def scale_zones(zones, width, height):
    """If zones.json was drawn on a different video size, scale all points to this video."""
    fw, fh = zones.get("frame_size", [width, height])
    if (fw, fh) == (width, height) or not fw or not fh:
        return zones
    sx, sy = width / fw, height / fh
    sc = lambda pts: [[p[0] * sx, p[1] * sy] for p in pts]
    for z in zones.get("restricted_zones", []):
        z["polygon"] = sc(z["polygon"])
    for z in zones.get("congestion_zones", []) + zones.get("ignore_zones", []):
        z["polygon"] = sc(z["polygon"])
    for z in zones.get("road_directions", []):
        z["polygon"] = sc(z["polygon"])
    for z in zones.get("lane_lines", []):
        z["points"] = sc(z["points"])
    if zones.get("calibration"):
        zones["calibration"]["points_px"] = sc(zones["calibration"]["points_px"])
    return zones
