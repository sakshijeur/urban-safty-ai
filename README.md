# Urban Safety AI 🚦🛡️

> **AI-Based Urban Road Safety & Traffic Intelligence System**

Urban Safety AI is a comprehensive intelligent traffic monitoring and safety audit application built with PySide6 (Qt) and Python. It features real-time object tracking, safety rule engines (near-miss detection, dangerous lane changes, sudden braking, wrong-side driving, and restricted area intrusion), emergency vehicle priority preemption, and safety analytics reporting.

---

## 🌟 Key Features

1. **Overview Dashboard**
   - Live KPI counters (Vehicles, Pedestrians, Near Misses, Sudden Braking, Wrong-Side, Restricted Entry, Emergency Vehicles, High-Risk Events).
   - Real-time Traffic Status alert banner (`LOW` / `MODERATE` / `HIGH`).
   - Dynamic Risk Heatmap with glowing thermal risk corridors and street networks.
   - Events Over Time line chart and Severity Mix donut chart.
   - End-to-end AI Pipeline status strip (`VIDEO` → `DETECT` → `TRACK` → `RULES` → `ALERTS`).
   - Interactive live Alert Feed.

2. **Live Monitoring (CCTV Control Room)**
   - Multi-camera feed selector (`[ A ]`, `[ B ]`, `[ C ]`).
   - Overlaid bounding boxes, classification badges, and road lane direction indicators.
   - Play/Pause, Record, Snapshot, Zoom, and Pan controls.
   - Object category filter buttons (Vehicles, Pedestrians, Bikes/Scooters, Emergency).
   - Real-time hazard telemetry monitor bars.

3. **Video Analysis**
   - Multi-object detection and safety audit player with frame scrubbers and variable speeds (`0.5x` to `2.0x`).
   - Visualized collision trajectory danger vectors between vehicles and vulnerable road users.
   - 5-track interactive event timeline.
   - 7-step AI Pipeline strip (`VIDEO CLIP` → `TARGET ACQ` → `VEHICLE CLF` → `TRACKING` → `TRAJECTORY` → `RISK AUDIT` → `REPORT/LOG`).
   - Configurable detection models (YOLOv8m, YOLOv8x, YOLOv8n) and trackers (ByteTrack, BoT-SORT).

4. **Risk Events**
   - Filterable event audit log (search, date range, zones, severity levels, and statuses).
   - Interactive Safety-Critical Proximity Diagram displaying real-time distance measurements (e.g. Car ⟷ Pedestrian ⟵ Bicycle).
   - Detailed event inspection panel with saved moment snapshots and workflow actions (`Acknowledge`, `Investigate`, `Resolve`, `Export`).

5. **Priority & Zones**
   - Live system date and real-time clock.
   - Emergency Vehicle Priority Simulation: Approaching emergency vehicle detection, traffic light status (`RED` to `GREEN` preemption override), and automated signal control.
   - Restricted-Zone Monitoring: Multi-zone polygon overlay (Restricted Zone, Emergency Lane, Pedestrian-Only, No-Entry Road Section) with vehicle intrusion detection.
   - Emergency vehicle response protocol legend (Ambulance, Fire Truck, Police Vehicle).

6. **Reports & Settings**
   - Traffic safety audit reports with intersection risk thermal heatmaps.
   - Time-series risk event trend analytics.
   - PDF, Executive Summary, and CSV data exports.
   - System settings panel with confidence threshold slider, detection limits, and safety rule engine toggles.

---

## 📂 Project Structure

```
Urban_Safety_AI/
├── app/
│   ├── main.py                   # Application entry point
│   ├── main_window.py            # Main application window & navigation
│   ├── live_page.py              # Live Monitoring CCTV screen
│   ├── video_analysis_page.py    # Video Analysis & safety audit screen
│   ├── priority_zones_page.py    # Emergency preemption & restricted zones
│   ├── reports_settings_page.py  # Traffic safety reports & system settings
│   ├── pages.py                  # Overview and Risk Events screens
│   ├── widgets.py                # Charts, diagrams, heatmaps, and KPI cards
│   ├── theme.py                  # Dark HUD design theme, palette & typography
│   ├── icons.py & icon_data.py   # Vector SVG Lucide icon library
│   ├── analysis.py               # Video processing & worker thread
│   ├── fake_data.py              # Event store & demo simulation engine
│   └── database.py               # SQLite run session & snapshot database
├── tracking/
│   ├── tracker.py                # Multi-object ByteTrack implementation
│   ├── risk.py                   # Safety risk computation engine
│   ├── config.py                 # Tracking configuration parameters
│   ├── geometry.py               # Spatial distance & intersection helpers
│   ├── zones_io.py & zones.json  # Camera zone definitions & calibrations
│   └── requirements.txt          # Tracking module requirements
├── data/
│   ├── safety.db                 # SQLite database for analysis runs
│   └── snapshots/                # Event snapshots and camera feeds
└── README.md
```

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+ (Recommended Python 3.11)
- Git

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/sakshijeur/urban-safty-ai.git
   cd urban-safty-ai
   ```

2. Install dependencies:
   ```bash
   pip install PySide6 opencv-python numpy
   ```

3. (Optional) If running custom tracking and YOLO models:
   ```bash
   pip install ultralytics
   ```

---

## 🖥️ Running the Application

### 1. Interactive Demo Mode (Instant Visualization)
Runs the application with simulated live event streams, preloaded camera feeds, and real-time dashboard updates:
```bash
cd app
python main.py --demo
```

### 2. Live Production Mode
Runs the application connected to SQLite database persistence, video files, or webcam feeds:
```bash
cd app
python main.py
```

---

## 📄 License
This project is developed for educational and research purposes under the Urban Safety AI Initiative.
