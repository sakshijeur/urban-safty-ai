"""Shared settings for the tracking module (Member 2). Change values here, not in the code."""
import os

TRACKING_DIR = os.path.dirname(os.path.abspath(__file__))   # the folder this file lives in


# Exact class names agreed by the whole team (handbook section 10.3)
TEAM_CLASSES = ["car", "bike", "bus", "truck", "auto", "ambulance", "fire_truck", "police", "person"]

# The standard COCO model uses different names. Map them to the team names.
# A custom model (models/best.pt) already uses team names, so it needs no mapping.
COCO_TO_TEAM = {"car": "car", "motorcycle": "bike", "bicycle": "bike",
                "bus": "bus", "truck": "truck", "person": "person"}

# Names shown on the video label bar
DISPLAY_NAME = {"car": "Car", "bike": "Bike", "bus": "Bus", "truck": "Truck", "auto": "Auto",
                "ambulance": "Ambulance", "fire_truck": "FireTruck", "police": "Police", "person": "Ped", "rider": "Rider"}

# Theme colors (handbook 11.2). OpenCV uses BGR order, so these are reversed from the hex codes.
GREEN  = (113, 204, 46)    # #2ECC71 normal
YELLOW = (15, 196, 241)    # #F1C40F warning
RED    = (79, 77, 255)     # #FF4D4F danger
BLUE   = (255, 167, 63)    # #3FA7FF emergency / info
PURPLE = (255, 107, 166)   # #A66BFF restricted zone
TEXT_DARK = (48, 30, 14)   # near-black navy for text on bright label bars

EMERGENCY_CLASSES = {"ambulance", "fire_truck", "police"}

# Tracking settings
MODEL_PATH = "yolov8m.pt"          # bigger = finds more. Slow laptop? use "yolov8s.pt". Later: models/best.pt from Member 1
TRACKER = os.path.join(TRACKING_DIR, "bytetrack_custom.yaml")  # our settings; or "botsort.yaml"
CONF_THRESHOLD = 0.20            # lower = finds more objects (but more false ones)
PER_CLASS_CONF = {"person": 0.15}  # lower for small or distant objects
IMGSZ = 960                        # bigger = sees small/far objects. Try 1280 for crowded scenes
IOU = 0.5                          # overlap limit between boxes
HISTORY_LENGTH = 45                # last 30-60 positions kept per ID
SMOOTH_WINDOW = 5                  # moving average over this many points
MAX_MISSING_SECONDS = 1.0          # drop tracks missing longer than this
STOPPED_SPEED_KMH = 2.0

# Calibration: pixels -> meters. Until zones.json has 4 points, speed is shown in px/s.

# Crowded scenes: cut each frame into tiles so small, far vehicles are found (slower).
# Can also be switched on with:  python tracker.py --tiles
TILED = False
TILE_COLS, TILE_ROWS = 2, 2
# Label voting: a vehicle keeps the label it was given most often (stops car/truck flicker)
LABEL_VOTING = True

# Calibration is OFF until you have a clip that can be calibrated well.
# While off, speed shows in px/s (the handbook allows this). Set True after running calibrate.py.
USE_CALIBRATION = False

# Wrong-side driving (handbook: angle above ~135 degrees for N frames, one event per vehicle)
WRONG_SIDE_ANGLE = 135
WRONG_SIDE_FRAMES = 15
MIN_MOVE_PX = 15          # ignore vehicles that barely move (stopped or jittering)

# Biggest size of the video window on screen (only changes what you see)
DISPLAY_MAX = (1280, 720)

# Wrong detections (for example a mailbox called a car)
MIN_TRACK_FRAMES = 3      # an object must be seen this many frames before it is shown (stops flicker)
SHOW_CONF = False         # True (or --show-conf) adds the AI's confidence to each label, to pick cutoffs
# Raise a class cutoff if it makes false detections, for example: PER_CLASS_CONF = {"person": 0.15, "car": 0.35}

# ---- Risk rules (risk.py). Distances are in "box heights" of the objects, times in seconds,
# so the rules work without calibration. Tune these on your own clips.
NEAR_MISS_GAP = 0.5        # feet closer than this many box heights ...
TTC_HIGH, TTC_MEDIUM = 0.8, 1.5   # ... and time-to-collision under 1.5 s = near miss (under 0.8 s = HIGH)
VV_TTC, VP_TTC = 2.0, 2.5  # vehicle-vehicle and vehicle-pedestrian risk look a bit further ahead
PAIR_SEARCH = 4.0          # only check pairs closer than this many box heights
MIN_CLOSING_H = 0.8        # must approach faster than this many box heights per second
RIDER_REL_H = 0.6          # a person overlapping a bike and moving with it is a rider, not a risk
COLLISION_OVERLAP = 0.2    # boxes overlapping this much while approaching = possible collision
CORRIDOR_SECONDS, CORRIDOR_WIDTH = 2.0, 0.9   # path ahead of a vehicle: seconds of travel, width in vehicle widths
EVENT_COOLDOWN_S = 5.0     # the same event for the same object is not repeated for this long
BRAKE_MIN_SPEED_H = 1.5    # only vehicles moving faster than this many heights per second can brake suddenly
BRAKE_DROP = 0.5           # speed lost (50%) within the window below
BRAKE_WINDOW = (0.15, 0.7) # seconds ago: compare the current speed with the peak in this window
LANE_LATERAL_H = 0.8       # sideways speed (box heights per second) for a fast lane change
STOPPED_H = 0.3            # slower than this many heights per second counts as stopped
CONG_MOD_COUNT, CONG_HIGH_COUNT, CONG_STOPPED_FRAC, CONG_HOLD_S = 8, 14, 0.4, 3.0

# ---- Fewer false alarms
RISK_MIN_AGE = 10          # an object must be tracked this many frames before any risk rule looks at it
CONFIRM_FRAMES = 3         # a risk must hold for this many frames in a row before it becomes an event
VEL_FRAMES = 10            # speed is measured over this many frames (smooths the shaking of the boxes)
VEL_DEADBAND_H = 0.4       # slower than this many box heights per second counts as standing still
FOOT_FRACTION = 0.3        # the "feet" of an object = the bottom 30% of its box (a car behind another car is not touching it)

# ---- Riders: a "person" sitting on a bike is a rider, not a pedestrian
PED_MAX_SPEED_H = 2.5      # a "person" moving faster than this many box heights per second is on a vehicle
RIDER_SCORE = 4            # each frame on a bike (or too fast) adds 2, each frame off removes 1; this score = rider
