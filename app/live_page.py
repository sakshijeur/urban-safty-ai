"""Live Monitoring screen: open a video (or webcam), watch detections, toggle cameras, object classes, and hazard telemetry."""
import os
from PySide6.QtCore import Qt, QRectF, QPointF, QSize, Signal, QTimer
from PySide6.QtGui import QPainter, QColor, QPainterPath, QPen, QFont, QPixmap, QBrush
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox, QFileDialog,
                               QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QFrame)
import theme
import icons
from fake_data import EVENT_INFO
from widgets import Panel, StatCard, AlertFeed, event_color, EVENT_ICON
from pages import page_title
from analysis import AnalysisWorker

COUNTERS = [("vehicles", "Vehicles", "car"), ("pedestrians", "Pedestrians", "person-standing"),
            ("near_misses", "Near Misses", "car-front"), ("sudden_braking", "Sudden Braking", "octagon-alert"),
            ("wrong_side", "Wrong-Side", "circle-plus")]
STATE_COLOR = {"IDLE": "#5B6B82", "LIVE": theme.GREEN, "PAUSED": theme.YELLOW, "DONE": theme.BLUE}


class EnhancedVideoView(QWidget):
    """Shows live video frames with camera overlays, bounding boxes, lane arrows, and telemetry."""
    def __init__(self):
        super().__init__()
        self.image = None
        self.state = "LIVE"
        self.camera_id = "A"
        self.zoom = 1.0
        self.show_vehicles = True
        self.show_pedestrians = True
        self.show_bikes = True
        self.show_emergency = True
        self.setMinimumSize(480, 290)

        # Preload camera frames from data/snapshots
        self.cam_frames = {}
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data", "snapshots")
        for cam, fn in [("A", "s3_f39.jpg"), ("B", "s2_f10.jpg"), ("C", "s4_f12.jpg")]:
            p = os.path.join(data_dir, fn)
            if os.path.exists(p):
                self.cam_frames[cam] = QPixmap(p)

    def set_camera(self, cam_id):
        self.camera_id = cam_id
        self.update()

    def set_image(self, img):
        self.image = img
        self.update()

    def set_state(self, state):
        self.state = state
        self.update()

    def clear(self):
        self.image = None
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        clip = QPainterPath()
        clip.addRoundedRect(QRectF(0, 0, w, h), 8, 8)
        p.setClipPath(clip)

        # Draw base video or snapshot
        if self.image is not None:
            scaled = self.image.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            p.drawImage((w - scaled.width()) // 2, (h - scaled.height()) // 2, scaled)
        elif self.camera_id in self.cam_frames and not self.cam_frames[self.camera_id].isNull():
            pm = self.cam_frames[self.camera_id]
            scaled = pm.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            sx = (scaled.width() - w) // 2
            sy = (scaled.height() - h) // 2
            p.drawPixmap(0, 0, scaled, sx, sy, w, h)
        else:
            p.fillRect(0, 0, w, h, QColor("#03070F"))
            p.drawPixmap(w // 2 - 24, h // 2 - 44, icons.pixmap("video", theme.BORDER_HI, 48, 1.4))
            p.setPen(QColor(theme.DIM))
            p.drawText(QRectF(0, h / 2 + 14, w, 24), Qt.AlignCenter, "Live CCTV Stream")

        # Overlay bounding boxes (matching Page 2)
        if self.image is None and self.camera_id == "A":
            # 1. Ambulance (Emergency)
            if self.show_emergency:
                ax, ay, aw, ah = int(w * 0.16), int(h * 0.35), int(w * 0.14), int(h * 0.25)
                p.setBrush(theme.qcolor(theme.RED, 20))
                p.setPen(QPen(QColor(theme.RED), 2))
                p.drawRect(ax, ay, aw, ah)
                # tag
                p.setBrush(QColor(theme.RED))
                p.setPen(Qt.NoPen)
                p.drawRoundedRect(QRectF(ax, ay - 16, 28, 16), 3, 3)
                p.drawPixmap(ax + 5, ay - 14, icons.pixmap("ambulance", "#FFFFFF", 12))

            # 2. White car (Vehicles)
            if self.show_vehicles:
                cx, cy, cw, ch = int(w * 0.36), int(h * 0.40), int(w * 0.10), int(h * 0.18)
                p.setBrush(theme.qcolor(theme.CYAN, 20))
                p.setPen(QPen(QColor(theme.CYAN), 2))
                p.drawRect(cx, cy, cw, ch)
                p.setBrush(QColor(theme.CYAN))
                p.setPen(Qt.NoPen)
                p.drawRoundedRect(QRectF(cx, cy - 16, 42, 16), 3, 3)
                p.setPen(QColor("black"))
                p.setFont(QFont("Segoe UI", 7, QFont.Bold))
                p.drawText(QRectF(cx, cy - 16, 42, 16), Qt.AlignCenter, "Car #2")

            # 3. Scooter / Bike
            if self.show_bikes:
                bx, by, bw, bh = int(w * 0.51), int(h * 0.38), int(w * 0.08), int(h * 0.18)
                p.setBrush(theme.qcolor(theme.GREEN, 20))
                p.setPen(QPen(QColor(theme.GREEN), 2))
                p.drawRect(bx, by, bw, bh)
                p.setBrush(QColor(theme.GREEN))
                p.setPen(Qt.NoPen)
                p.drawRoundedRect(QRectF(bx, by - 16, 42, 16), 3, 3)
                p.setPen(QColor("black"))
                p.setFont(QFont("Segoe UI", 7, QFont.Bold))
                p.drawText(QRectF(bx, by - 16, 42, 16), Qt.AlignCenter, "Bike #7")

            # 4. Pedestrian
            if self.show_pedestrians:
                px, py, pw, ph = int(w * 0.65), int(h * 0.42), int(w * 0.07), int(h * 0.20)
                p.setBrush(theme.qcolor(theme.YELLOW, 20))
                p.setPen(QPen(QColor(theme.YELLOW), 2))
                p.drawRect(px, py, pw, ph)
                p.setBrush(QColor(theme.YELLOW))
                p.setPen(Qt.NoPen)
                p.drawRoundedRect(QRectF(px, py - 16, 38, 16), 3, 3)
                p.setPen(QColor("black"))
                p.setFont(QFont("Segoe UI", 7, QFont.Bold))
                p.drawText(QRectF(px, py - 16, 38, 16), Qt.AlignCenter, "Ped #4")

        # Bottom Lane Direction Arrows Overlaid on Road
        lane_y = h - 36
        p.setFont(QFont("Segoe UI", 12, QFont.Bold))
        p.setPen(QColor(255, 255, 255, 180))
        for i, arrow in enumerate(["↑", "↑", "↑", "↰", "↶"]):
            lx = int(w * 0.15 + i * w * 0.16)
            p.drawText(QRectF(lx, lane_y, 30, 24), Qt.AlignCenter, arrow)

        p.setClipping(False)

        # Top Right Status Chip
        color = QColor(STATE_COLOR.get(self.state, theme.DIM))
        f = QFont(p.font())
        f.setBold(True)
        f.setPointSize(8)
        p.setFont(f)
        cw = 24 + p.fontMetrics().horizontalAdvance(self.state) + 14
        chip = QRectF(14, 14, cw, 24)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(2, 8, 21, 210))
        p.drawRoundedRect(chip, 12, 12)
        p.setBrush(color)
        p.drawEllipse(QRectF(chip.left() + 10, chip.center().y() - 4, 8, 8))
        p.setPen(QColor("white"))
        p.drawText(QRectF(chip.left() + 24, chip.top(), chip.width() - 24, chip.height()), Qt.AlignVCenter | Qt.AlignLeft, self.state)


class RightHazardBar(QFrame):
    """Right-side vertical hazard monitors with progress levels matching Page 2."""
    def __init__(self):
        super().__init__()
        self.setFixedWidth(56)
        self.setStyleSheet(f"background: #040D1C; border: 1px solid {theme.BORDER}; border-radius: 8px;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 12, 6, 12)
        lay.setSpacing(14)

        # Top funnel icon
        f_ic = QLabel()
        f_ic.setPixmap(icons.pixmap("funnel", theme.CYAN, 18))
        f_ic.setAlignment(Qt.AlignCenter)
        lay.addWidget(f_ic)

        # 5 hazard icons with status level bars
        hazards = [
            ("car", theme.YELLOW, 0.7),
            ("car-front", theme.RED, 0.9),
            ("siren", theme.RED, 0.85),
            ("ban", theme.YELLOW, 0.5),
            ("circle-alert", theme.YELLOW, 0.6),
        ]
        for icon_name, col, lvl in hazards:
            item = QVBoxLayout()
            item.setSpacing(4)
            item.setAlignment(Qt.AlignCenter)

            ic = QLabel()
            ic.setFixedSize(32, 32)
            ic.setAlignment(Qt.AlignCenter)
            ic.setPixmap(icons.pixmap(icon_name, col, 18))
            ic.setStyleSheet(f"background: {theme.rgba(col, 35)}; border: 1px solid {theme.rgba(col, 90)}; border-radius: 16px;")

            bar = QFrame()
            bar.setFixedSize(30, 4)
            bar.setStyleSheet(f"background: {col}; border-radius: 2px;")

            item.addWidget(ic)
            item.addWidget(bar)
            lay.addLayout(item)

        lay.addStretch(1)


class LiveMonitorPage(QWidget):
    event_clicked = Signal(int)

    def __init__(self, store):
        super().__init__()
        self.store, self.worker = store, None
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(10)

        head = page_title("Live Monitoring", "Live CCTV with real-time detection, camera switching and alerts")
        self.sub_label = head.sub_label
        root.addLayout(head)

        # Top action bar
        bar = QHBoxLayout()
        bar.setSpacing(8)
        self.btn_open = self.button("  Open Video", "primary", "clapperboard")
        self.btn_cam = self.button("  Webcam", "ghost", "camera")
        self.btn_pause = self.button("  Pause", "ghost", "pause")
        self.btn_stop = self.button("  Stop", "danger", "square")
        self.tiles = QCheckBox("Crowded mode (tiled detection)")

        bar.addWidget(self.btn_open)
        bar.addWidget(self.btn_cam)
        bar.addWidget(self.btn_pause)
        bar.addWidget(self.btn_stop)
        bar.addSpacing(12)
        bar.addWidget(self.tiles)
        bar.addStretch(1)
        root.addLayout(bar)

        # Main horizontal layout: Video section + Hazard bar
        main = QHBoxLayout()
        main.setSpacing(12)

        # Center Video Container
        vbox = QVBoxLayout()
        vbox.setSpacing(8)

        # Video frame panel with top camera selection buttons
        vp = Panel("")
        vp.body.setContentsMargins(8, 8, 8, 8)

        # Camera selection row inside player header
        cam_row = QHBoxLayout()
        cam_row.setSpacing(6)
        cam_label = QLabel("CAMERA FEED:")
        cam_label.setObjectName("cardLabel")
        cam_row.addWidget(cam_label)

        self.cam_btns = {}
        for c in ["A", "B", "C"]:
            b = QPushButton(c)
            b.setObjectName("tabBtn")
            b.setCheckable(True)
            b.setFixedSize(34, 28)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _c=False, cam=c: self.switch_camera(cam))
            self.cam_btns[c] = b
            cam_row.addWidget(b)
        self.cam_btns["A"].setChecked(True)

        cam_row.addStretch(1)
        btn_snap_top = QPushButton()
        btn_snap_top.setObjectName("ghost")
        btn_snap_top.setIcon(icons.icon("camera", "#FFFFFF", 14))
        btn_snap_top.setFixedSize(30, 28)
        btn_fs_top = QPushButton()
        btn_fs_top.setObjectName("ghost")
        btn_fs_top.setIcon(icons.icon("maximize", "#FFFFFF", 14))
        btn_fs_top.setFixedSize(30, 28)
        cam_row.addWidget(btn_snap_top)
        cam_row.addWidget(btn_fs_top)

        vp.body.addLayout(cam_row)

        self.view = EnhancedVideoView()
        vp.body.addWidget(self.view, 1)

        # Video playback toolbar below view (matching Page 2)
        ctrl_bar = QHBoxLayout()
        ctrl_bar.setSpacing(8)

        self.btn_play_pause = QPushButton()
        self.btn_play_pause.setObjectName("ghost")
        self.btn_play_pause.setIcon(icons.icon("pause", "#FFFFFF", 16))
        self.btn_play_pause.setFixedSize(36, 32)
        self.btn_play_pause.clicked.connect(self.toggle_pause)

        self.btn_record = QPushButton()
        self.btn_record.setObjectName("ghost")
        self.btn_record.setIcon(icons.icon("circle-plus", "#FF4D4F", 16))
        self.btn_record.setFixedSize(36, 32)
        self.btn_record.setToolTip("Record Stream")

        self.btn_snap = QPushButton()
        self.btn_snap.setObjectName("ghost")
        self.btn_snap.setIcon(icons.icon("camera", "#FFFFFF", 16))
        self.btn_snap.setFixedSize(36, 32)
        self.btn_snap.setToolTip("Take Snapshot")

        ctrl_bar.addWidget(self.btn_play_pause)
        ctrl_bar.addWidget(self.btn_record)
        ctrl_bar.addWidget(self.btn_snap)
        ctrl_bar.addSpacing(10)

        # Zoom buttons
        z_lbl = QLabel("ZOOM:")
        z_lbl.setObjectName("cardLabel")
        ctrl_bar.addWidget(z_lbl)
        b_zmin = QPushButton("-")
        b_zmin.setObjectName("ghost")
        b_zmin.setFixedSize(28, 28)
        b_zplus = QPushButton("+")
        b_zplus.setObjectName("ghost")
        b_zplus.setFixedSize(28, 28)
        ctrl_bar.addWidget(b_zmin)
        ctrl_bar.addWidget(b_zplus)

        ctrl_bar.addSpacing(10)
        p_lbl = QLabel("PAN:")
        p_lbl.setObjectName("cardLabel")
        ctrl_bar.addWidget(p_lbl)
        b_pmin = QPushButton("-")
        b_pmin.setObjectName("ghost")
        b_pmin.setFixedSize(28, 28)
        b_pplus = QPushButton("+")
        b_pplus.setObjectName("ghost")
        b_pplus.setFixedSize(28, 28)
        ctrl_bar.addWidget(b_pmin)
        ctrl_bar.addWidget(b_pplus)

        ctrl_bar.addStretch(1)
        dot_live = QLabel()
        dot_live.setFixedSize(10, 10)
        dot_live.setStyleSheet(f"background: {theme.GREEN}; border-radius: 5px;")
        ctrl_bar.addWidget(dot_live)

        vp.body.addLayout(ctrl_bar)
        vbox.addWidget(vp, 1)

        # Circular Object Category Toggles (matching bottom of Page 2)
        cat_row = QHBoxLayout()
        cat_row.setSpacing(18)
        cat_row.setAlignment(Qt.AlignCenter)

        self.cat_btns = {}
        for key, name, icon_name, col in [
            ("veh", "Vehicles", "car", theme.CYAN),
            ("ped", "Pedestrians", "person-standing", theme.GREEN),
            ("bike", "Bikes/Scooters", "bike", theme.CYAN),
            ("emg", "Emergency", "ambulance", "#FF8A1F")
        ]:
            b = QPushButton()
            b.setCheckable(True)
            b.setChecked(True)
            b.setFixedSize(48, 48)
            b.setCursor(Qt.PointingHandCursor)
            b.setIcon(icons.icon(icon_name, col, 22))
            b.setIconSize(QSize(22, 22))
            b.setStyleSheet(f"""
                QPushButton {{ background: {theme.rgba(col, 30)}; border: 2px solid {theme.rgba(col, 140)}; border-radius: 24px; }}
                QPushButton:checked {{ background: {theme.rgba(col, 70)}; border: 2px solid {col}; }}
                QPushButton:hover {{ border: 2px solid white; }}
            """)
            b.setToolTip(f"Toggle {name} Overlay")
            b.clicked.connect(lambda _c=False, k=key: self.toggle_category(k))
            self.cat_btns[key] = b
            cat_row.addWidget(b)

        vbox.addLayout(cat_row)
        main.addLayout(vbox, 1)

        # Right-side Hazard Monitor Bar (matching Page 2)
        self.hazard_bar = RightHazardBar()
        main.addWidget(self.hazard_bar)

        root.addLayout(main, 1)

        # Connect actions
        self.btn_open.clicked.connect(self.choose_video)
        self.btn_cam.clicked.connect(lambda: self.start("webcam"))
        self.btn_pause.clicked.connect(self.toggle_pause)
        self.btn_stop.clicked.connect(self.stop)

    def switch_camera(self, cam_id):
        for c, b in self.cam_btns.items():
            b.setChecked(c == cam_id)
        self.view.set_camera(cam_id)

    def toggle_category(self, cat):
        if cat == "veh":
            self.view.show_vehicles = self.cat_btns[cat].isChecked()
        elif cat == "ped":
            self.view.show_pedestrians = self.cat_btns[cat].isChecked()
        elif cat == "bike":
            self.view.show_bikes = self.cat_btns[cat].isChecked()
        elif cat == "emg":
            self.view.show_emergency = self.cat_btns[cat].isChecked()
        self.view.update()

    @staticmethod
    def button(text, style, icon_name):
        b = QPushButton(text)
        b.setObjectName(style)
        b.setIcon(icons.icon(icon_name, "#FFFFFF", 16))
        b.setCursor(Qt.PointingHandCursor)
        return b

    def choose_video(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose a video", "", "Video (*.mp4 *.avi *.mov *.mkv *.m4v);;All files (*)")
        if path:
            self.start(path)

    def start(self, source):
        self.stop()
        self.store.reset()
        self.view.clear()
        sid = self.store.begin_session("Webcam" if source == "webcam" else os.path.basename(source))
        self.worker = AnalysisWorker(source, self.tiles.isChecked(), snap_dir=self.store.db.snap_dir if self.store.db else None, session_id=sid or 0)
        w = self.worker
        w.summary.connect(self.store.end_session)
        w.frame_ready.connect(self.view.set_image)
        w.events_ready.connect(self.store.ingest)
        w.traffic_ready.connect(self.store.set_traffic)
        w.counts_ready.connect(self.store.set_totals)
        w.state_changed.connect(self.on_state)
        w.start()
        self.set_running(True)

    def toggle_pause(self):
        if self.worker is not None and self.worker.isRunning():
            self.worker.toggle_pause()
        else:
            new_state = "PAUSED" if self.view.state == "LIVE" else "LIVE"
            self.view.set_state(new_state)
            self.btn_play_pause.setIcon(icons.icon("play" if new_state == "PAUSED" else "pause", "#FFFFFF", 16))

    def stop(self):
        if self.worker is not None:
            self.worker.stop()
            self.worker = None
        self.set_running(False)
        self.view.set_state("IDLE")

    def set_running(self, running):
        self.btn_open.setEnabled(not running)
        self.btn_cam.setEnabled(not running)
        self.btn_pause.setEnabled(running)
        self.btn_stop.setEnabled(running)
        self.tiles.setEnabled(not running)

    def on_state(self, state):
        self.view.set_state(state)
        self.btn_pause.setText("  Resume" if state == "PAUSED" else "  Pause")
        self.btn_pause.setIcon(icons.icon("play" if state == "PAUSED" else "pause", "#FFFFFF", 16))
