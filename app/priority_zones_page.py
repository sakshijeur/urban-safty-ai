"""Priority & Zones screen: emergency vehicle simulation and restricted-area intrusion control."""
import os
import time
from PySide6.QtCore import Qt, QRectF, QPointF, QTimer, QTime, QDate
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QPainterPath, QLinearGradient, QFont, QPixmap
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
                               QGridLayout, QSizePolicy)
import theme
import icons
from widgets import Panel


def page_header_with_clock(title_text, subtitle_text):
    """Page title on left, live date & time on right."""
    wrap = QHBoxLayout()
    col = QVBoxLayout()
    col.setSpacing(2)
    t = QLabel(title_text.upper())
    t.setFont(theme.heading_font(28))
    t.setStyleSheet("color: white; letter-spacing: 0.5px;")
    s = QLabel(subtitle_text)
    s.setObjectName("dim")
    col.addWidget(t)
    col.addWidget(s)
    wrap.addLayout(col, 1)

    time_box = QVBoxLayout()
    time_box.setSpacing(2)
    d_lbl = QLabel(QDate.currentDate().toString("dd MMM yyyy").upper())
    d_lbl.setObjectName("dim")
    d_lbl.setAlignment(Qt.AlignRight)
    d_lbl.setStyleSheet(f"color: {theme.DIM}; font-size: 11px; {theme.STRONG_CSS}")

    clock_lbl = QLabel(QTime.currentTime().toString("HH:mm:ss"))
    clock_lbl.setAlignment(Qt.AlignRight)
    clock_lbl.setFont(theme.heading_font(20))
    clock_lbl.setStyleSheet(f"color: white; letter-spacing: 1px;")

    time_box.addWidget(d_lbl)
    time_box.addWidget(clock_lbl)
    wrap.addLayout(time_box)

    # timer to update clock
    clock_timer = QTimer(t)
    clock_timer.setInterval(1000)
    clock_timer.timeout.connect(lambda: (
        d_lbl.setText(QDate.currentDate().toString("dd MMM yyyy").upper()),
        clock_lbl.setText(QTime.currentTime().toString("HH:mm:ss"))
    ))
    clock_timer.start()

    wrap.sub_label = s
    return wrap


class EmergencySimCanvas(QWidget):
    """Canvas showing road intersection with approaching ambulance and traffic lights."""
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(240)
        self.preempted = False
        self.ambulance_y = 0.75  # 0.75 = approaching, 0.25 = crossing
        self.beacon_on = True

        self.pulse_timer = QTimer(self)
        self.pulse_timer.setInterval(300)
        self.pulse_timer.timeout.connect(self.toggle_beacon)
        self.pulse_timer.start()

    def toggle_beacon(self):
        self.beacon_on = not self.beacon_on
        self.update()

    def set_preempted(self, state):
        self.preempted = state
        self.ambulance_y = 0.35 if state else 0.75
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        clip = QPainterPath()
        clip.addRoundedRect(QRectF(0, 0, w, h), 8, 8)
        p.setClipPath(clip)

        # Background asphalt
        p.fillRect(0, 0, w, h, QColor("#030814"))

        # Road surface
        rw = min(w * 0.75, 420)
        rx = (w - rw) / 2
        p.fillRect(QRectF(rx, 0, rw, h), QColor("#081424"))

        # Lane markings
        p.setPen(QPen(QColor("#1A3048"), 1.5, Qt.DashLine))
        for frac in [0.25, 0.5, 0.75]:
            lx = rx + rw * frac
            p.drawLine(QPointF(lx, 0), QPointF(lx, h))

        # Intersection stop line
        stop_y = h * 0.38
        p.setPen(QPen(QColor("#2A486A"), 3))
        p.drawLine(QPointF(rx, stop_y), QPointF(rx + rw, stop_y))

        # Crosswalk lines
        p.setPen(QPen(QColor("#16283D"), 2))
        for step in range(0, int(rw), 24):
            p.drawLine(QPointF(rx + step, stop_y - 20), QPointF(rx + step + 12, stop_y - 20))

        # Traffic Signal Light Box
        sig_x, sig_y = rx + rw + 14, stop_y - 36
        if sig_x + 30 <= w:
            p.setBrush(QColor("#03060C"))
            p.setPen(QPen(QColor("#182E47"), 1.5))
            p.drawRoundedRect(QRectF(sig_x, sig_y, 24, 52), 4, 4)

            # Red light
            red_color = QColor("#FF4D4F") if not self.preempted else QColor("#4A1517")
            p.setBrush(red_color)
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(sig_x + 12, sig_y + 14), 7, 7)

            # Green light
            grn_color = QColor("#2ECC71") if self.preempted else QColor("#0C361D")
            p.setBrush(grn_color)
            p.drawEllipse(QPointF(sig_x + 12, sig_y + 38), 7, 7)

        # Ambulance Vehicle
        amb_w, amb_h = 44, 76
        amb_x = rx + rw * 0.5 - amb_w / 2
        amb_y = h * self.ambulance_y - amb_h / 2

        # Vehicle body
        p.setBrush(QColor("#FFFFFF"))
        p.setPen(QPen(QColor("#FF4D4F"), 2))
        p.drawRoundedRect(QRectF(amb_x, amb_y, amb_w, amb_h), 6, 6)

        # Windshield
        p.setBrush(QColor("#102235"))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(amb_x + 4, amb_y + 6, amb_w - 8, 16), 3, 3)

        # Red Cross on roof
        p.setBrush(QColor("#FF4D4F"))
        p.drawRect(QRectF(amb_x + amb_w / 2 - 3, amb_y + 32, 6, 20))
        p.drawRect(QRectF(amb_x + amb_w / 2 - 10, amb_y + 39, 20, 6))

        # Flashing beacon lights
        beacon_c = QColor("#FF4D4F" if self.beacon_on else "#3FA7FF")
        p.setBrush(beacon_c)
        p.drawEllipse(QPointF(amb_x + 10, amb_y + 24), 4, 4)
        p.setBrush(QColor("#3FA7FF" if self.beacon_on else "#FF4D4F"))
        p.drawEllipse(QPointF(amb_x + amb_w - 10, amb_y + 24), 4, 4)

        # Glow ring around beacon
        g = QRadialGradient(QPointF(amb_x + amb_w / 2, amb_y + 24), 40)
        g.setColorAt(0, theme.qcolor("#FF4D4F" if self.beacon_on else "#3FA7FF", 70))
        g.setColorAt(1, theme.qcolor("#FF4D4F", 0))
        p.setBrush(QBrush(g))
        p.drawEllipse(QPointF(amb_x + amb_w / 2, amb_y + 24), 40, 40)

        # Ambulance label
        p.setPen(QColor("black"))
        p.setFont(QFont("Segoe UI", 8, QFont.Bold))
        p.drawText(QRectF(amb_x, amb_y + amb_h - 18, amb_w, 14), Qt.AlignCenter, "AMB #2")

        # Approach trajectory path
        p.setPen(QPen(QColor(theme.GREEN if self.preempted else theme.CYAN), 1.5, Qt.DashLine))
        p.drawLine(QPointF(amb_x + amb_w / 2, amb_y), QPointF(amb_x + amb_w / 2, 0))


class RestrictedZoneCanvas(QWidget):
    """Overhead camera view with colored zone polygons and intrusion highlight."""
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(240)
        self.flash = False
        self.timer = QTimer(self)
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.on_flash)
        self.timer.start()

    def on_flash(self):
        self.flash = not self.flash
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        clip = QPainterPath()
        clip.addRoundedRect(QRectF(0, 0, w, h), 8, 8)
        p.setClipPath(clip)

        p.fillRect(0, 0, w, h, QColor("#030814"))

        # Road intersection geometry
        rw = min(w * 0.8, 440)
        rx = (w - rw) / 2
        p.fillRect(QRectF(rx, 0, rw, h), QColor("#071526"))

        # Zone 2: Emergency Lane (Green dashed border, transparent green fill)
        em_lane = QRectF(rx + rw * 0.72, 0, rw * 0.25, h)
        p.setBrush(theme.qcolor(theme.GREEN, 25))
        p.setPen(QPen(QColor(theme.GREEN), 1.5, Qt.DashLine))
        p.drawRect(em_lane)
        p.setPen(QColor(theme.GREEN))
        p.setFont(QFont("Segoe UI", 8, QFont.Bold))
        p.drawText(em_lane, Qt.AlignHCenter | Qt.AlignTop, "Emergency Lane")

        # Zone 3: Pedestrian-only area (Yellow dashed box)
        ped_area = QRectF(rx + 10, h * 0.65, rw * 0.35, h * 0.30)
        p.setBrush(theme.qcolor(theme.YELLOW, 25))
        p.setPen(QPen(QColor(theme.YELLOW), 1.5, Qt.DashLine))
        p.drawRect(ped_area)
        p.setPen(QColor(theme.YELLOW))
        p.drawText(ped_area, Qt.AlignHCenter | Qt.AlignTop, "Pedestrian-only area")

        # Zone 4: No-entry road section (Purple dashed box)
        no_entry = QRectF(rx + rw * 0.55, h * 0.68, rw * 0.40, h * 0.28)
        p.setBrush(theme.qcolor(theme.PURPLE, 25))
        p.setPen(QPen(QColor(theme.PURPLE), 1.5, Qt.DashLine))
        p.drawRect(no_entry)
        p.setPen(QColor(theme.PURPLE))
        p.drawText(no_entry, Qt.AlignHCenter | Qt.AlignTop, "No-entry road section")

        # Zone 1: Restricted Zone 01 (Red dashed box)
        rz = QRectF(rx + rw * 0.22, h * 0.15, rw * 0.45, h * 0.38)
        fill_alpha = 45 if self.flash else 25
        p.setBrush(theme.qcolor(theme.RED, fill_alpha))
        p.setPen(QPen(QColor(theme.RED), 2, Qt.DashLine))
        p.drawRect(rz)
        p.setPen(QColor(theme.RED))
        p.drawText(QRectF(rz.left(), rz.top() + 6, rz.width(), 16), Qt.AlignCenter, "Restricted Zone 01")

        # Intruding vehicle inside Restricted Zone 01
        car_w, car_h = 32, 54
        cx = rz.center().x() - car_w / 2
        cy = rz.center().y() - car_h / 2 + 10
        p.setBrush(QColor("#C8D6E5"))
        p.setPen(QPen(QColor(theme.RED), 2))
        p.drawRoundedRect(QRectF(cx, cy, car_w, car_h), 5, 5)

        # Flashing red bounding box
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(theme.RED), 2 if self.flash else 1))
        p.drawRect(QRectF(cx - 6, cy - 6, car_w + 12, car_h + 12))

        # Tag
        p.setBrush(QColor(theme.RED))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(cx - 6, cy - 20, 68, 15), 3, 3)
        p.setPen(QColor("white"))
        p.setFont(QFont("Segoe UI", 7, QFont.Bold))
        p.drawText(QRectF(cx - 6, cy - 20, 68, 15), Qt.AlignCenter, "VHC-84921")


class PriorityZonesPage(QWidget):
    def __init__(self, store):
        super().__init__()
        self.store = store
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        header = page_header_with_clock("Priority & Zones", "Emergency vehicle simulation and restricted-area intrusion control")
        self.sub_label = header.sub_label
        root.addLayout(header)

        # Two main columns: Left = Priority Sim, Right = Restricted Zone
        main_cols = QHBoxLayout()
        main_cols.setSpacing(14)

        # ---- LEFT: Emergency Vehicle Priority Simulation
        left_panel = Panel("Emergency Vehicle Priority Simulation")
        lp = QVBoxLayout()
        lp.setSpacing(10)

        top_bar = QHBoxLayout()
        sim_tag = QLabel("SIMULATION ONLY")
        sim_tag.setStyleSheet(f"background: {theme.rgba(theme.RED, 50)}; color: {theme.RED}; border: 1px solid {theme.RED}; border-radius: 4px; padding: 2px 8px; {theme.STRONG_CSS} font-size: 10px;")
        loc_lbl = QLabel("Location Camera Zone A")
        loc_lbl.setObjectName("dim")
        top_bar.addWidget(loc_lbl)
        top_bar.addStretch(1)
        top_bar.addWidget(sim_tag)
        lp.addLayout(top_bar)

        self.sim_canvas = EmergencySimCanvas()
        lp.addWidget(self.sim_canvas, 1)

        # Status Table / Grid
        grid = QGridLayout()
        grid.setSpacing(8)

        def make_row(row_idx, label, value_widget):
            l = QLabel(label)
            l.setObjectName("dim")
            grid.addWidget(l, row_idx, 0)
            grid.addWidget(value_widget, row_idx, 1)

        v1 = QLabel("Ambulance #2")
        v1.setStyleSheet(f"color: white; {theme.STRONG_CSS}")
        make_row(0, "Emergency Vehicle", v1)

        v2 = QLabel("A")
        v2.setStyleSheet(f"color: white; {theme.STRONG_CSS}")
        make_row(1, "Location Camera Zone", v2)

        v3 = QLabel("North")
        v3.setStyleSheet(f"color: white; {theme.STRONG_CSS}")
        make_row(2, "Direction", v3)

        v4 = QLabel("Approaching intersection")
        v4.setStyleSheet(f"color: {theme.YELLOW}; {theme.STRONG_CSS}")
        make_row(3, "Status", v4)

        self.sig_curr = QLabel("RED")
        self.sig_curr.setAlignment(Qt.AlignCenter)
        self.sig_curr.setFixedSize(70, 22)
        self.sig_curr.setStyleSheet(f"background: {theme.rgba(theme.RED, 70)}; color: {theme.RED}; border: 1px solid {theme.RED}; border-radius: 4px; {theme.STRONG_CSS} font-size: 11px;")
        make_row(4, "Current Signal", self.sig_curr)

        self.sig_ai = QLabel("GREEN")
        self.sig_ai.setAlignment(Qt.AlignCenter)
        self.sig_ai.setFixedSize(70, 22)
        self.sig_ai.setStyleSheet(f"background: {theme.rgba(theme.GREEN, 70)}; color: {theme.GREEN}; border: 1px solid {theme.GREEN}; border-radius: 4px; {theme.STRONG_CSS} font-size: 11px;")
        make_row(5, "AI Recommendation", self.sig_ai)

        lp.addLayout(grid)

        # Control Action Buttons
        btn_box = QHBoxLayout()
        btn_box.setSpacing(8)

        self.btn_approve = QPushButton("  Approve Simulation")
        self.btn_approve.setObjectName("success")
        self.btn_approve.setIcon(icons.icon("check", "#FFFFFF", 16))
        self.btn_approve.clicked.connect(self.approve_sim)

        self.btn_cancel = QPushButton("  Cancel")
        self.btn_cancel.setObjectName("danger")
        self.btn_cancel.setIcon(icons.icon("x", "#FFFFFF", 16))
        self.btn_cancel.clicked.connect(self.cancel_sim)

        self.btn_view = QPushButton("  View Approach")
        self.btn_view.setObjectName("ghost")
        self.btn_view.setIcon(icons.icon("eye", "#FFFFFF", 16))
        self.btn_view.clicked.connect(self.view_approach)

        btn_box.addWidget(self.btn_approve)
        btn_box.addWidget(self.btn_cancel)
        btn_box.addWidget(self.btn_view)
        lp.addLayout(btn_box)

        left_panel.body.addLayout(lp)
        main_cols.addWidget(left_panel, 1)

        # ---- RIGHT: Restricted-Zone Monitoring
        right_panel = Panel("Restricted-Zone Monitoring")
        rp = QVBoxLayout()
        rp.setSpacing(10)

        # Zone Legend Badges
        legend_row = QHBoxLayout()
        legend_row.setSpacing(8)
        for name, col in [("Restricted Zone 01", theme.RED), ("Emergency Lane", theme.GREEN),
                          ("Pedestrian-only", theme.YELLOW), ("No-entry section", theme.PURPLE)]:
            item = QHBoxLayout()
            item.setSpacing(4)
            sq = QLabel()
            sq.setFixedSize(10, 10)
            sq.setStyleSheet(f"background: {col}; border-radius: 2px;")
            txt = QLabel(name)
            txt.setStyleSheet(f"color: {theme.DIM}; font-size: 10px; {theme.STRONG_CSS}")
            item.addWidget(sq)
            item.addWidget(txt)
            legend_row.addLayout(item)
        rp.addLayout(legend_row)

        self.zone_canvas = RestrictedZoneCanvas()
        rp.addWidget(self.zone_canvas, 1)

        # Alert Card
        alert_box = QFrame()
        alert_box.setStyleSheet(f"background: {theme.rgba('#1A0808', 210)}; border: 1px solid {theme.rgba(theme.RED, 140)}; border-radius: 8px; padding: 10px;")
        abl = QVBoxLayout(alert_box)
        abl.setSpacing(8)

        head_a = QHBoxLayout()
        warn_ic = QLabel()
        warn_ic.setPixmap(icons.pixmap("triangle-alert", theme.RED, 20))
        warn_t = QLabel("Restricted-zone entry detected")
        warn_t.setStyleSheet(f"color: {theme.RED}; {theme.STRONG_CSS} font-size: 13px;")
        head_a.addWidget(warn_ic)
        head_a.addWidget(warn_t, 1)
        abl.addLayout(head_a)

        agrid = QGridLayout()
        agrid.setSpacing(6)

        def add_alert_row(idx, k, v):
            kl = QLabel(k)
            kl.setObjectName("dim")
            vl = QLabel(v)
            vl.setStyleSheet(f"color: white; {theme.STRONG_CSS} font-size: 11px;")
            agrid.addWidget(kl, idx, 0)
            agrid.addWidget(vl, idx, 1)

        add_alert_row(0, "Object ID", "VHC-84921")
        add_alert_row(1, "Timestamp", "17 MAY 2025  10:24:31")
        add_alert_row(2, "Zone Name", "Restricted Zone 01")
        add_alert_row(3, "Entry Direction", "Southbound")
        abl.addLayout(agrid)

        rp.addWidget(alert_box)
        right_panel.body.addLayout(rp)
        main_cols.addWidget(right_panel, 1)

        root.addLayout(main_cols, 1)

        # ---- BOTTOM: Emergency Vehicle Legend Strip
        legend_panel = Panel("Emergency Vehicle Legend")
        strip = QHBoxLayout()
        strip.setSpacing(16)

        vehicles = [
            ("AMBULANCE", "ambulance", theme.RED, "Code 3 Priority - Full Traffic Preemption"),
            ("FIRE TRUCK", "truck", "#FF8A1F", "Heavy Equipment - Emergency Corridor Clearance"),
            ("POLICE VEHICLE", "shield", theme.CYAN, "Rapid Response - Interception & Escort Protocol")
        ]

        for title, icon_name, color, desc in vehicles:
            card = QFrame()
            card.setStyleSheet(f"background: {theme.ROW}; border: 1px solid {theme.BORDER}; border-radius: 8px; padding: 8px 12px;")
            cl = QHBoxLayout(card)
            cl.setSpacing(12)

            ic = QLabel()
            ic.setFixedSize(36, 36)
            ic.setAlignment(Qt.AlignCenter)
            ic.setPixmap(icons.pixmap(icon_name, color, 24))
            ic.setStyleSheet(f"background: {theme.rgba(color, 35)}; border-radius: 18px;")

            meta = QVBoxLayout()
            meta.setSpacing(2)
            t_lbl = QLabel(title)
            t_lbl.setStyleSheet(f"color: white; {theme.STRONG_CSS} font-size: 12px;")
            d_lbl = QLabel(desc)
            d_lbl.setObjectName("dim")
            d_lbl.setStyleSheet(f"color: {theme.DIM}; font-size: 10px;")
            meta.addWidget(t_lbl)
            meta.addWidget(d_lbl)

            cl.addWidget(ic)
            cl.addLayout(meta, 1)
            strip.addWidget(card, 1)

        legend_panel.body.addLayout(strip)
        root.addWidget(legend_panel)

    def approve_sim(self):
        self.sim_canvas.set_preempted(True)
        self.sig_curr.setText("GREEN")
        self.sig_curr.setStyleSheet(f"background: {theme.rgba(theme.GREEN, 70)}; color: {theme.GREEN}; border: 1px solid {theme.GREEN}; border-radius: 4px; {theme.STRONG_CSS} font-size: 11px;")

    def cancel_sim(self):
        self.sim_canvas.set_preempted(False)
        self.sig_curr.setText("RED")
        self.sig_curr.setStyleSheet(f"background: {theme.rgba(theme.RED, 70)}; color: {theme.RED}; border: 1px solid {theme.RED}; border-radius: 4px; {theme.STRONG_CSS} font-size: 11px;")

    def view_approach(self):
        self.sim_canvas.set_preempted(not self.sim_canvas.preempted)
