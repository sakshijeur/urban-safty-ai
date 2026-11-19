"""Video Analysis screen: upload a clip, run the safety analysis, inspect the timeline and trajectory."""
import os
import random
from PySide6.QtCore import Qt, QRectF, QPointF, QTimer, Signal
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QPainterPath, QLinearGradient, QFont, QPixmap
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider, QComboBox,
                               QCheckBox, QProgressBar, QFrame, QSizePolicy, QFileDialog)
import theme
import icons
from widgets import Panel

def get_page_title(text, subtitle):
    box = QVBoxLayout()
    box.setSpacing(2)
    t = QLabel(text.upper())
    t.setFont(theme.heading_font(28))
    t.setStyleSheet("color: white; letter-spacing: 0.5px;")
    s = QLabel(subtitle)
    s.setObjectName("dim")
    box.addWidget(t)
    box.addWidget(s)
    box.sub_label = s
    return box


class AnalysisVideoViewport(QWidget):
    """Visualizer for video playback with bounding boxes, labels, and trajectory lines."""
    def __init__(self):
        super().__init__()
        self.setMinimumSize(480, 280)
        self.frame_idx = 0
        self.total_frames = 1500
        self.playing = False
        self.boxes = [
            {"id": "ID: 8", "type": "car", "color": "#F1C40F", "rect": (0.39, 0.22, 0.08, 0.08)},
            {"id": "ID: 19", "type": "car", "color": "#09B0F1", "rect": (0.49, 0.18, 0.05, 0.06)},
            {"id": "ID: 25", "type": "car", "color": "#3FA7FF", "rect": (0.57, 0.24, 0.08, 0.09)},
            {"id": "ID: 31", "type": "bike", "color": "#00D2D3", "rect": (0.40, 0.35, 0.07, 0.14)},
            {"id": "ID: 41", "type": "ped", "color": "#FF4D4F", "rect": (0.64, 0.32, 0.06, 0.16)},
            {"id": "ID: 12", "type": "car", "color": "#2ECC71", "rect": (0.22, 0.28, 0.11, 0.11)},
        ]
        # find sample snapshot if available
        self.snapshot_pm = None
        for fn in ["s3_f39.jpg", "s3_f12.jpg", "s2_f10.jpg"]:
            path = os.path.join(os.path.dirname(__file__), "..", "data", "snapshots", fn)
            if os.path.exists(path):
                self.snapshot_pm = QPixmap(path)
                break

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        clip = QPainterPath()
        clip.addRoundedRect(QRectF(0, 0, w, h), 8, 8)
        p.setClipPath(clip)

        if self.snapshot_pm and not self.snapshot_pm.isNull():
            scaled = self.snapshot_pm.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            sx = (scaled.width() - w) // 2
            sy = (scaled.height() - h) // 2
            p.drawPixmap(0, 0, scaled, sx, sy, w, h)
            # dark overlay for high contrast
            p.fillRect(0, 0, w, h, QColor(2, 8, 21, 140))
        else:
            p.fillRect(0, 0, w, h, QColor("#03070F"))
            # Road perspective lines
            p.setPen(QPen(QColor("#16283D"), 2))
            p.drawLine(int(w * 0.45), 0, int(w * 0.1), h)
            p.drawLine(int(w * 0.55), 0, int(w * 0.9), h)
            p.drawLine(int(w * 0.5), 0, int(w * 0.5), h)

        # Danger trajectory line between ID 41 (pedestrian) and vehicles
        p.setPen(QPen(QColor("#FF4D4F"), 2, Qt.DashLine))
        ped_pt = QPointF(w * 0.67, h * 0.40)
        bike_pt = QPointF(w * 0.435, h * 0.42)
        car_pt = QPointF(w * 0.43, h * 0.26)
        p.drawLine(ped_pt, bike_pt)
        p.drawLine(ped_pt, car_pt)

        # Draw trajectory glow dots
        for pt in [ped_pt, bike_pt, car_pt]:
            p.setBrush(QColor("#FF4D4F"))
            p.setPen(Qt.NoPen)
            p.drawEllipse(pt, 4, 4)

        # Draw bounding boxes and tags
        for b in self.boxes:
            bx = int(w * b["rect"][0])
            by = int(h * b["rect"][1])
            bw = int(w * b["rect"][2])
            bh = int(h * b["rect"][3])
            col = QColor(b["color"])

            # Box
            p.setBrush(QColor(col.red(), col.green(), col.blue(), 30))
            p.setPen(QPen(col, 2))
            p.drawRect(bx, by, bw, bh)

            # Tag badge
            tag_text = b["id"]
            p.setFont(QFont("Segoe UI", 8, QFont.Bold))
            tw = p.fontMetrics().horizontalAdvance(tag_text) + 8
            th = 16
            p.setBrush(col)
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(QRectF(bx, by - th, tw, th), 3, 3)
            p.setPen(QColor("black" if b["color"] in ["#F1C40F", "#2ECC71", "#00D2D3"] else "white"))
            p.drawText(QRectF(bx, by - th, tw, th), Qt.AlignCenter, tag_text)

        # Fullscreen icon at top right
        p.setClipping(False)


class MultiTrackTimeline(QWidget):
    """5-track timeline matching Page 3 with colored dots and event icons."""
    def __init__(self):
        super().__init__()
        self.setFixedHeight(130)
        self.tracks = [
            ("Normal Flow", theme.GREEN, "car", [0.08, 0.25, 0.45, 0.68, 0.85]),
            ("Lane Departure", theme.YELLOW, "car", [0.15, 0.52, 0.73]),
            ("Sudden Braking", "#FF8A1F", "triangle-alert", [0.32, 0.61, 0.90]),
            ("Pedestrian Risk", theme.RED, "triangle-alert", [0.42, 0.78]),
            ("Near Miss", theme.RED, "octagon-alert", [0.48, 0.82]),
        ]

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        p.fillRect(0, 0, w, h, QColor("#040C1A"))
        row_h = (h - 20) / len(self.tracks)

        for i, (name, color, icon_name, points) in enumerate(self.tracks):
            cy = 15 + i * row_h
            # Lead dot
            p.setBrush(QColor(color))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(20, cy), 4.5, 4.5)

            # Icon
            pm = icons.pixmap(icon_name, color, 14)
            p.drawPixmap(34, int(cy - 7), pm)

            # Track background line
            p.setPen(QPen(QColor("#0F2038"), 1))
            p.drawLine(QPointF(65, cy), QPointF(w - 20, cy))

            # Event tick marks on track
            track_w = w - 85
            for frac in points:
                ex = 65 + frac * track_w
                p.setBrush(QColor(color))
                p.setPen(QPen(QColor("#040C1A"), 1.5))
                p.drawEllipse(QPointF(ex, cy), 4, 4)


class AnalysisPipelineStrip(Panel):
    """7-step AI Pipeline strip matching Page 3."""
    STEPS = [
        ("video", "VIDEO CLIP"),
        ("crosshair", "TARGET ACQ"),
        ("car", "VEHICLE CLF"),
        ("locate", "TRACKING"),
        ("route", "TRAJECTORY"),
        ("triangle-alert", "RISK AUDIT"),
        ("file-text", "REPORT/LOG")
    ]

    def __init__(self):
        super().__init__("")
        self.canvas = _Pipeline7Canvas(self.STEPS)
        self.body.addWidget(self.canvas)


class _Pipeline7Canvas(QWidget):
    def __init__(self, steps):
        super().__init__()
        self.steps = steps
        self.setMinimumHeight(84)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, n = self.width(), len(self.steps)
        cy, r = 32, 22
        xs = [w * (i + 0.5) / n for i in range(n)]

        for i in range(n - 1):
            x0, x1 = xs[i] + r + 8, xs[i + 1] - r - 8
            p.setPen(QPen(QColor(theme.CYAN), 1.5, Qt.DashLine))
            p.drawLine(QPointF(x0, cy), QPointF(x1 - 5, cy))
            p.setPen(QPen(QColor(theme.CYAN), 1.8))
            p.drawLine(QPointF(x1 - 6, cy - 4), QPointF(x1, cy))
            p.drawLine(QPointF(x1 - 6, cy + 4), QPointF(x1, cy))

        for (name, label), x in zip(self.steps, xs):
            is_risk = name in ["triangle-alert", "file-text"]
            accent = theme.RED if name == "triangle-alert" else theme.CYAN
            g = QLinearGradient(x - r, cy - r, x + r, cy + r)
            g.setColorAt(0, theme.qcolor(accent, 40))
            g.setColorAt(1, theme.qcolor(accent, 8))
            p.setBrush(QBrush(g))
            p.setPen(QPen(QColor(accent), 1.5))
            p.drawEllipse(QPointF(x, cy), r, r)

            pm = icons.pixmap(name, accent, 20)
            p.drawPixmap(int(x - 10), int(cy - 10), pm)

            p.setPen(QColor(theme.DIM))
            f = p.font()
            f.setPointSize(7)
            f.setBold(True)
            p.setFont(f)
            p.drawText(QRectF(x - 45, cy + r + 4, 90, 14), Qt.AlignCenter, label)


class VideoAnalysisPage(QWidget):
    inspect_requested = Signal()

    def __init__(self, store):
        super().__init__()
        self.store = store
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        title_box = get_page_title("Video Analysis", "Multi-object detection, trajectory tracking, and safety audit")
        self.sub_label = title_box.sub_label
        root.addLayout(title_box)

        content = QHBoxLayout()
        content.setSpacing(14)

        # Left / Center column: Video player + controls + timeline + pipeline
        left = QVBoxLayout()
        left.setSpacing(10)

        # Video viewport
        player_panel = Panel("")
        player_panel.body.setContentsMargins(10, 10, 10, 10)
        self.viewport = AnalysisVideoViewport()
        player_panel.body.addWidget(self.viewport, 1)

        # Video controls bar
        ctrl = QHBoxLayout()
        ctrl.setSpacing(8)

        self.btn_play = QPushButton()
        self.btn_play.setObjectName("primary")
        self.btn_play.setIcon(icons.icon("play", "#FFFFFF", 16))
        self.btn_play.setFixedSize(36, 34)
        self.btn_play.clicked.connect(self.toggle_play)

        self.btn_back = QPushButton()
        self.btn_back.setObjectName("ghost")
        self.btn_back.setIcon(icons.icon("skip-back", "#FFFFFF", 16))
        self.btn_back.setFixedSize(34, 34)
        self.btn_back.clicked.connect(lambda: self.step_frame(-30))

        self.btn_fwd = QPushButton()
        self.btn_fwd.setObjectName("ghost")
        self.btn_fwd.setIcon(icons.icon("skip-forward", "#FFFFFF", 16))
        self.btn_fwd.setFixedSize(34, 34)
        self.btn_fwd.clicked.connect(lambda: self.step_frame(30))

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 1000)
        self.slider.setValue(240)
        self.slider.valueChanged.connect(self.on_slider)

        self.speed_box = QComboBox()
        self.speed_box.addItems(["1.0x", "0.5x", "1.5x", "2.0x"])
        self.speed_box.setFixedWidth(78)

        self.btn_snap = QPushButton()
        self.btn_snap.setObjectName("ghost")
        self.btn_snap.setIcon(icons.icon("camera", "#FFFFFF", 16))
        self.btn_snap.setFixedSize(34, 34)
        self.btn_snap.setToolTip("Capture Snapshot")

        self.btn_fs = QPushButton()
        self.btn_fs.setObjectName("ghost")
        self.btn_fs.setIcon(icons.icon("maximize", "#FFFFFF", 16))
        self.btn_fs.setFixedSize(34, 34)
        self.btn_fs.setToolTip("Fullscreen")

        ctrl.addWidget(self.btn_play)
        ctrl.addWidget(self.btn_back)
        ctrl.addWidget(self.btn_fwd)
        ctrl.addWidget(self.slider, 1)
        ctrl.addWidget(self.speed_box)
        ctrl.addWidget(self.btn_snap)
        ctrl.addWidget(self.btn_fs)
        player_panel.body.addLayout(ctrl)

        # Telemetry info bar
        info_row = QHBoxLayout()
        dot = QLabel()
        dot.setFixedSize(8, 8)
        dot.setStyleSheet(f"background: {theme.GREEN}; border-radius: 4px;")
        self.t_cur = QLabel("12:31:04")
        self.t_cur.setStyleSheet(f"color: white; {theme.STRONG_CSS} font-size: 11px;")
        self.t_range = QLabel("12:31:05 / 12:45:30")
        self.t_range.setStyleSheet(f"color: {theme.DIM}; font-size: 11px;")
        self.fps_label = QLabel("12 FPS")
        self.fps_label.setStyleSheet(f"color: {theme.CYAN}; {theme.STRONG_CSS} font-size: 11px;")

        info_row.addWidget(dot)
        info_row.addWidget(self.t_cur)
        info_row.addSpacing(14)
        info_row.addWidget(self.t_range)
        info_row.addStretch(1)
        info_row.addWidget(self.fps_label)
        player_panel.body.addLayout(info_row)

        left.addWidget(player_panel, 1)

        # Multi-track timeline
        tl_panel = Panel("Interactive Event Timeline")
        self.timeline = MultiTrackTimeline()
        tl_panel.body.addWidget(self.timeline)
        left.addWidget(tl_panel)

        # Pipeline
        self.pipeline = AnalysisPipelineStrip()
        left.addWidget(self.pipeline)

        content.addLayout(left, 1)

        # Right sidebar: Analysis settings & Run
        right = Panel("Analysis Configuration")
        right.setFixedWidth(310)

        rl = QVBoxLayout()
        rl.setSpacing(12)

        lbl1 = QLabel("VIDEO SOURCE")
        lbl1.setObjectName("cardLabel")
        self.source_box = QComboBox()
        self.source_box.addItems(["15300538-hd_1920_1080_60fps.mp4",
                                  "18669275-uhd_3840_2160_30fps.mp4",
                                  "Intersection_Downtown_01.mp4",
                                  "Custom Upload..."])
        rl.addWidget(lbl1)
        rl.addWidget(self.source_box)

        lbl2 = QLabel("MODEL ARCHITECTURE")
        lbl2.setObjectName("cardLabel")
        self.model_box = QComboBox()
        self.model_box.addItems(["YOLOv8m (Balanced - Recommended)",
                                 "YOLOv8x (High Precision)",
                                 "YOLOv8n (Real-Time Edge)"])
        rl.addWidget(lbl2)
        rl.addWidget(self.model_box)

        lbl3 = QLabel("TRACKING ALGORITHM")
        lbl3.setObjectName("cardLabel")
        self.tracker_box = QComboBox()
        self.tracker_box.addItems(["ByteTrack (Standard Multi-Object)",
                                   "BoT-SORT (Camera Motion Corr)"])
        rl.addWidget(lbl3)
        rl.addWidget(self.tracker_box)

        lbl4 = QLabel("AUDIT PROFILE")
        lbl4.setObjectName("cardLabel")
        self.profile_box = QComboBox()
        self.profile_box.addItems(["Full Urban Safety Audit",
                                   "Near-Miss & Trajectory Collision",
                                   "Restricted Zone & Lane Violation"])
        rl.addWidget(lbl4)
        rl.addWidget(self.profile_box)

        lbl5 = QLabel("ZONE PRESET")
        lbl5.setObjectName("cardLabel")
        self.zone_box = QComboBox()
        self.zone_box.addItems(["Cam-01 Main Intersection",
                                "Cam-02 Pedestrian Crossing",
                                "Cam-03 Expressway North"])
        rl.addWidget(lbl5)
        rl.addWidget(self.zone_box)

        self.tiled_chk = QCheckBox("Enable Crowded / Tiled Mode")
        self.tiled_chk.setChecked(True)
        rl.addWidget(self.tiled_chk)

        rl.addSpacing(10)
        self.pbar = QProgressBar()
        self.pbar.setFixedHeight(8)
        self.pbar.setTextVisible(False)
        self.pbar.setStyleSheet(f"QProgressBar {{ background: #0E1E32; border-radius: 4px; }} QProgressBar::chunk {{ background: {theme.ACCENT}; border-radius: 4px; }}")
        self.pbar.hide()
        rl.addWidget(self.pbar)

        self.btn_run = QPushButton("  Run Safety Analysis")
        self.btn_run.setObjectName("primary")
        self.btn_run.setIcon(icons.icon("play", "#FFFFFF", 16))
        self.btn_run.setFixedHeight(44)
        self.btn_run.clicked.connect(self.run_analysis)
        rl.addWidget(self.btn_run)

        self.btn_inspect = QPushButton("  Inspect In Risk Events")
        self.btn_inspect.setObjectName("ghost")
        self.btn_inspect.setIcon(icons.icon("file-text", "#FFFFFF", 16))
        self.btn_inspect.setFixedHeight(38)
        self.btn_inspect.clicked.connect(self.inspect_requested.emit)
        rl.addWidget(self.btn_inspect)

        rl.addStretch(1)
        right.body.addLayout(rl)
        content.addWidget(right)

        root.addLayout(content, 1)

        # Simulation playback timer
        self.play_timer = QTimer(self)
        self.play_timer.setInterval(100)
        self.play_timer.timeout.connect(self.on_tick)

        # Run analysis progress timer
        self.run_timer = QTimer(self)
        self.run_timer.setInterval(80)
        self.run_timer.timeout.connect(self.on_analysis_progress)
        self.sim_progress = 0

    def toggle_play(self):
        if self.play_timer.isActive():
            self.play_timer.stop()
            self.btn_play.setIcon(icons.icon("play", "#FFFFFF", 16))
        else:
            self.play_timer.start()
            self.btn_play.setIcon(icons.icon("pause", "#FFFFFF", 16))

    def on_tick(self):
        v = (self.slider.value() + 2) % self.slider.maximum()
        self.slider.setValue(v)

    def on_slider(self, val):
        secs = int(val * 0.75)
        m = secs // 60
        s = secs % 60
        self.t_cur.setText(f"12:{31 + m:02d}:{s:02d}")

    def step_frame(self, delta):
        self.slider.setValue(max(0, min(self.slider.maximum(), self.slider.value() + delta)))

    def run_analysis(self):
        self.btn_run.setEnabled(False)
        self.btn_run.setText("  Analyzing Video...")
        self.pbar.show()
        self.pbar.setValue(0)
        self.sim_progress = 0
        self.run_timer.start()

    def on_analysis_progress(self):
        self.sim_progress += 4
        self.pbar.setValue(self.sim_progress)
        if self.sim_progress >= 100:
            self.run_timer.stop()
            self.btn_run.setEnabled(True)
            self.btn_run.setText("  Run Safety Analysis")
            self.pbar.hide()
            # notify user or inject event
            if self.store:
                self.store.add_event({
                    "type": "NEAR_MISS",
                    "severity": "CRITICAL",
                    "objects": "Car #12 <-> Ped #4, Bike #7",
                    "zone": "Zone 3",
                    "frame": 240,
                    "time": "12:31:05",
                    "details": "distance 2.4m, speed delta 38 km/h"
                })
