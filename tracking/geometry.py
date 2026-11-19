"""Small math helpers: ground point, heading, direction, homography."""
import math
import numpy as np
import cv2

DIRECTIONS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]

def ground_point(x1, y1, x2, y2):
    """Bottom-center of a box: where the object touches the road."""
    return (x1 + x2) / 2.0, y2

def heading_deg(dx, dy):
    """0 = up the screen (N), clockwise. Screen y points down, so dy is flipped."""
    return (math.degrees(math.atan2(dx, -dy)) + 360) % 360

def direction_name(angle):
    """Turn an angle into N, NE, E, SE, S, SW, W or NW."""
    return DIRECTIONS[int((angle + 22.5) // 45) % 8]

def build_homography(calibration):
    """calibration = {'points_px': [[x,y]x4], 'points_m': [[x,y]x4]}.
    Returns a 3x3 matrix, or None when not calibrated yet."""
    if not calibration:
        return None
    src = np.array(calibration.get("points_px", []), dtype=np.float32)
    dst = np.array(calibration.get("points_m", []), dtype=np.float32)
    if len(src) != 4 or len(dst) != 4:
        return None
    return cv2.getPerspectiveTransform(src, dst)

def to_meters(H, x, y):
    """Convert a pixel point to road meters. Returns the same point if H is None."""
    if H is None:
        return x, y
    p = cv2.perspectiveTransform(np.array([[[x, y]]], dtype=np.float32), H)[0][0]
    return float(p[0]), float(p[1])

def distance_m(H, p1, p2):
    """Real-world distance in meters between two pixel points on the road (needs calibration)."""
    a, b = to_meters(H, *p1), to_meters(H, *p2)
    return float(np.hypot(a[0] - b[0], a[1] - b[1]))
