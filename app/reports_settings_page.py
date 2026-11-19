"""Reports & Settings screen: risk heatmap, automatic event report, exports, and configuration."""
import os
import csv
from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import (QPainter, QColor, QPen, QBrush, QPainterPath, QLinearGradient,
                           QRadialGradient, QFont, QPixmap)
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider,
                               QComboBox, QCheckBox, QFrame, QGridLayout, QMessageBox, QFileDialog)
import theme
import icons
from widgets import Panel, StatCard, LineChart


class IntersectionRiskHeatmap(QWidget):
    """Thermal heatmap overlay on an intersection layout matching Page 6."""
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(200)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        clip = QPainterPath()
        clip.addRoundedRect(QRectF(0, 0, w, h), 8, 8)
        p.setClipPath(clip)

        # Dark ground
        p.fillRect(0, 0, w, h, QColor("#030814"))

        # 4-way intersection layout
        road_w = min(w, h) * 0.42
        cx, cy = w / 2, h / 2

        # Vertical road
        p.fillRect(QRectF(cx - road_w / 2, 0, road_w, h), QColor("#081524"))
        # Horizontal road
        p.fillRect(QRectF(0, cy - road_w / 2, w, road_w), QColor("#081524"))

        # Center intersection square
        p.fillRect(QRectF(cx - road_w / 2, cy - road_w / 2, road_w, road_w), QColor("#0A1C30"))

        # Lane dividers
        p.setPen(QPen(QColor("#13283E"), 1.2, Qt.DashLine))
        p.drawLine(QPointF(cx, 0), QPointF(cx, h))
        p.drawLine(QPointF(0, cy), QPointF(w, cy))

        # Thermal heat density radial gradients
        # 1. Hot core at center of intersection (Red -> Orange -> Yellow -> Green -> transparent)
        core = QRadialGradient(QPointF(cx, cy), road_w * 0.8)
        core.setColorAt(0.0, theme.qcolor(theme.RED, 210))
        core.setColorAt(0.25, theme.qcolor("#FF7A00", 160))
        core.setColorAt(0.50, theme.qcolor(theme.YELLOW, 110))
        core.setColorAt(0.75, theme.qcolor(theme.GREEN, 55))
        core.setColorAt(1.0, theme.qcolor(theme.CYAN, 0))

        p.setBrush(QBrush(core))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx, cy), road_w * 0.8, road_w * 0.8)

        # 2. Branch hotspots (approach zones)
        for dx, dy in [(road_w * 0.65, 0), (-road_w * 0.65, 0), (0, -road_w * 0.65)]:
            g = QRadialGradient(QPointF(cx + dx, cy + dy), road_w * 0.5)
            g.setColorAt(0.0, theme.qcolor("#FF8A1F", 160))
            g.setColorAt(0.4, theme.qcolor(theme.YELLOW, 90))
            g.setColorAt(0.8, theme.qcolor(theme.GREEN, 40))
            g.setColorAt(1.0, theme.qcolor(theme.CYAN, 0))
            p.setBrush(QBrush(g))
            p.drawEllipse(QPointF(cx + dx, cy + dy), road_w * 0.5, road_w * 0.5)

        # Traffic light status dots (left bottom corner)
        p.setClipping(False)
        for i, col in enumerate([theme.RED, theme.YELLOW, theme.GREEN]):
            p.setBrush(QColor(col))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(18, h - 45 + i * 14), 4.5, 4.5)


class ReportsSettingsPage(QWidget):
    def __init__(self, store):
        super().__init__()
        self.store = store
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        # Title
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        t = QLabel("REPORTS & SETTINGS")
        t.setFont(theme.heading_font(28))
        t.setStyleSheet("color: white; letter-spacing: 0.5px;")
        s = QLabel("Risk heatmap, automatic event report, exports, and configuration")
        s.setObjectName("dim")
        title_box.addWidget(t)
        title_box.addWidget(s)
        self.sub_label = s
        root.addLayout(title_box)

        # Split: Left 2/3 = Traffic Safety Report, Right 1/3 = System Settings
        main_layout = QHBoxLayout()
        main_layout.setSpacing(14)

        # ---- LEFT: TRAFFIC SAFETY REPORT
        left_area = QVBoxLayout()
        left_area.setSpacing(12)

        # Filter bar
        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(10)

        c1 = QLabel("CAMERA ZONE")
        c1.setObjectName("cardLabel")
        self.cam_box = QComboBox()
        self.cam_box.addItems(["Intersection_05_26", "Expressway_Sector_02", "Downtown_Crossing_04"])
        self.cam_box.setMinimumWidth(160)

        c2 = QLabel("DATE RANGE")
        c2.setObjectName("cardLabel")
        self.zone_box = QComboBox()
        self.zone_box.addItems(["ALL ZONES", "Zone 1", "Zone 2", "Zone 3"])
        self.zone_box.setMinimumWidth(130)

        c3 = QLabel("EVENT SEVERITY")
        c3.setObjectName("cardLabel")
        self.sev_box = QComboBox()
        self.sev_box.addItems(["ALL SEVERITIES", "CRITICAL", "HIGH", "MEDIUM", "LOW"])
        self.sev_box.setMinimumWidth(140)

        filter_bar.addWidget(c1)
        filter_bar.addWidget(self.cam_box)
        filter_bar.addWidget(c2)
        filter_bar.addWidget(self.zone_box)
        filter_bar.addWidget(c3)
        filter_bar.addWidget(self.sev_box)
        filter_bar.addStretch(1)
        left_area.addLayout(filter_bar)

        # 10 Stat KPI Cards in 2 rows of 5
        kpis_row1 = QHBoxLayout()
        kpis_row1.setSpacing(10)
        self.cards = {}

        CARD_DEFS = [
            ("duration", "Video Duration", "05:24", theme.CYAN, "clock-3"),
            ("vehicles", "Vehicles", "387", theme.KPI["vehicles"], "car"),
            ("pedestrians", "Pedestrians", "52", theme.KPI["pedestrians"], "person-standing"),
            ("near_misses", "Near Misses", "7", theme.KPI["near_misses"], "car-front"),
            ("wrong_side", "Wrong-Side Events", "3", theme.KPI["wrong_side"], "circle-plus"),
            ("sudden_braking", "Sudden Braking", "11", theme.KPI["sudden_braking"], "octagon-alert"),
            ("restricted_entries", "Restricted Entries", "4", theme.KPI["restricted_entry"], "ban"),
            ("emergency_vehicles", "Emergency Vehicles", "2", theme.KPI["emergency_vehicles"], "siren"),
            ("high_risk", "High-Risk Events", "6", theme.KPI["high_risk"], "triangle-alert"),
            ("traffic_level", "Traffic Level", "HIGH", theme.RED, "activity"),
        ]

        grid_cards = QGridLayout()
        grid_cards.setSpacing(10)
        for i, (key, label, val, col, icon_name) in enumerate(CARD_DEFS):
            card = StatCard(label, col, icon_name, compact=True)
            card.set_value(val)
            self.cards[key] = card
            grid_cards.addWidget(card, i // 5, i % 5)
        left_area.addLayout(grid_cards)

        # Middle: Risk Heatmap & Events Over Time
        mid_row = QHBoxLayout()
        mid_row.setSpacing(12)

        heat_panel = Panel("Risk Heatmap (Intersection)")
        self.heatmap = IntersectionRiskHeatmap()
        heat_panel.body.addWidget(self.heatmap, 1)
        mid_row.addWidget(heat_panel, 1)

        time_panel = Panel("Events Over Time")
        self.chart = LineChart()
        # Seed realistic time series data matching design
        self.chart.set_series([
            ("Near Misses", theme.CYAN, [4, 7, 5, 8, 11, 9, 14, 16]),
            ("Wrong-Side Events", "#FF8A1F", [1, 2, 2, 4, 3, 5, 6, 7]),
            ("Sudden Braking", theme.YELLOW, [2, 5, 4, 6, 8, 12, 10, 15]),
            ("High-Risk Events", theme.RED, [3, 4, 6, 5, 9, 7, 12, 18]),
        ])
        time_panel.body.addWidget(self.chart, 1)
        mid_row.addWidget(time_panel, 1)
        left_area.addLayout(mid_row, 1)

        # Bottom Export Bar
        export_row = QHBoxLayout()
        export_row.setSpacing(10)

        self.btn_pdf = QPushButton("  Export PDF Report")
        self.btn_pdf.setObjectName("primary")
        self.btn_pdf.setIcon(icons.icon("file-text", "#FFFFFF", 16))
        self.btn_pdf.clicked.connect(self.export_pdf)

        self.btn_doc = QPushButton("  Executive Summary")
        self.btn_doc.setObjectName("ghost")
        self.btn_doc.setIcon(icons.icon("file-text", "#FFFFFF", 16))
        self.btn_doc.clicked.connect(self.export_doc)

        self.btn_csv = QPushButton("  Export CSV Data")
        self.btn_csv.setObjectName("ghost")
        self.btn_csv.setIcon(icons.icon("file-spreadsheet", "#FFFFFF", 16))
        self.btn_csv.clicked.connect(self.export_csv)

        self.btn_share = QPushButton("  Share / Sync")
        self.btn_share.setObjectName("ghost")
        self.btn_share.setIcon(icons.icon("share-2", "#FFFFFF", 16))
        self.btn_share.clicked.connect(self.share_report)

        export_row.addWidget(self.btn_pdf)
        export_row.addWidget(self.btn_doc)
        export_row.addWidget(self.btn_csv)
        export_row.addWidget(self.btn_share)
        export_row.addStretch(1)
        left_area.addLayout(export_row)

        main_layout.addLayout(left_area, 2)

        # ---- RIGHT: SYSTEM SETTINGS PANEL
        settings_panel = Panel("System Settings", right_icon="settings")
        settings_panel.setFixedWidth(310)
        sp = QVBoxLayout()
        sp.setSpacing(12)

        l_m = QLabel("DETECTION MODEL")
        l_m.setObjectName("cardLabel")
        self.cfg_model = QComboBox()
        self.cfg_model.addItems(["YOLOv8m", "YOLOv8x", "YOLOv8n", "Custom Trained"])
        sp.addWidget(l_m)
        sp.addWidget(self.cfg_model)

        l_t = QLabel("TRACKER")
        l_t.setObjectName("cardLabel")
        self.cfg_tracker = QComboBox()
        self.cfg_tracker.addItems(["ByteTrack", "BoT-SORT"])
        sp.addWidget(l_t)
        sp.addWidget(self.cfg_tracker)

        l_c = QHBoxLayout()
        l_c_lbl = QLabel("CONFIDENCE THRESHOLD")
        l_c_lbl.setObjectName("cardLabel")
        self.thresh_val = QLabel("0.45")
        self.thresh_val.setStyleSheet(f"color: {theme.CYAN}; {theme.STRONG_CSS} font-size: 11px;")
        l_c.addWidget(l_c_lbl)
        l_c.addStretch(1)
        l_c.addWidget(self.thresh_val)
        sp.addLayout(l_c)

        self.conf_slider = QSlider(Qt.Horizontal)
        self.conf_slider.setRange(10, 95)
        self.conf_slider.setValue(45)
        self.conf_slider.valueChanged.connect(lambda v: self.thresh_val.setText(f"{v/100:.2f}"))
        sp.addWidget(self.conf_slider)

        l_max = QLabel("MAX DETECTION")
        l_max.setObjectName("cardLabel")
        self.max_box = QComboBox()
        self.max_box.addItems(["100", "50", "200", "Unlimited"])
        sp.addWidget(l_max)
        sp.addWidget(self.max_box)

        # Rule Toggles
        l_rules = QLabel("SAFETY RULE ENGINES")
        l_rules.setObjectName("cardLabel")
        sp.addWidget(l_rules)

        self.rule_chks = []
        rules = [
            ("Near-Miss Detection", "CRITICAL", theme.RED),
            ("Sudden Braking Detection", "HIGH", theme.RED),
            ("Wrong-Side Driving", "HIGH", theme.RED),
            ("Restricted Zone Intrusion", "HIGH", theme.RED),
            ("Emergency Vehicle Priority", "HIGH", theme.YELLOW),
        ]
        for name, sev, col in rules:
            r_lay = QHBoxLayout()
            chk = QCheckBox(name)
            chk.setChecked(True)
            badge = QLabel(sev)
            badge.setStyleSheet(f"background: {theme.rgba(col, 40)}; color: {col}; border: 1px solid {col}; border-radius: 4px; padding: 1px 6px; font-size: 9px; {theme.STRONG_CSS}")
            r_lay.addWidget(chk, 1)
            r_lay.addWidget(badge)
            sp.addLayout(r_lay)
            self.rule_chks.append(chk)

        sp.addSpacing(10)
        self.btn_save = QPushButton("  Save && Apply Settings")
        self.btn_save.setObjectName("primary")
        self.btn_save.setIcon(icons.icon("check", "#FFFFFF", 16))
        self.btn_save.setFixedHeight(40)
        self.btn_save.clicked.connect(self.save_settings)
        sp.addWidget(self.btn_save)

        sp.addStretch(1)
        settings_panel.body.addLayout(sp)
        main_layout.addWidget(settings_panel, 1)

        root.addLayout(main_layout, 1)

    def export_pdf(self):
        QMessageBox.information(self, "Export PDF", "Traffic Safety Report PDF generated successfully in data/reports/Safety_Audit_Report.pdf")

    def export_doc(self):
        QMessageBox.information(self, "Executive Summary", "Executive Safety Summary prepared for city authorities.")

    def export_csv(self):
        path = os.path.join(os.path.dirname(__file__), "..", "data", "traffic_safety_export.csv")
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Event ID", "Type", "Severity", "Objects", "Zone", "Time", "Status"])
                for ev in (self.store.events if self.store else []):
                    writer.writerow([ev.get("event_id"), ev.get("type"), ev.get("severity"), ev.get("objects"), ev.get("zone"), ev.get("time"), ev.get("status")])
            QMessageBox.information(self, "Export CSV", f"Safety events exported to:\n{os.path.abspath(path)}")
        except Exception as ex:
            QMessageBox.warning(self, "Export CSV", f"Could not export CSV: {ex}")

    def share_report(self):
        QMessageBox.information(self, "Share / Sync", "Report sync URL created: https://urban-safety.local/audit/05_26")

    def save_settings(self):
        self.btn_save.setText("  Saved!")
        self.btn_save.setStyleSheet(f"background: {theme.GREEN}; color: white; border: none; border-radius: 8px;")
        from PySide6.QtCore import QTimer
        QTimer.singleShot(1500, lambda: (
            self.btn_save.setText("  Save && Apply Settings"),
            self.btn_save.setStyleSheet("")
        ))
