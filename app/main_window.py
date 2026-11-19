"""The main window: header on top, sidebar on the left, screens in the middle (styled like the design)."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
                               QStackedWidget, QButtonGroup, QFrame, QMessageBox)
from PySide6.QtCore import QSize
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QScrollArea
import theme
import icons
from pages import OverviewPage, RiskEventsPage
from live_page import LiveMonitorPage
from video_analysis_page import VideoAnalysisPage
from priority_zones_page import PriorityZonesPage
from reports_settings_page import ReportsSettingsPage

# Sidebar order is fixed by the handbook (11.1): name, icon
NAV = [("Overview", "gauge"), ("Live Monitoring", "video"), ("Video Analysis", "clapperboard"),
       ("Risk Events", "triangle-alert"), ("Priority & Zones", "siren"), ("Reports & Settings", "chart-column")]
TRAFFIC = {"LOW": (theme.GREEN, "circle-check"), "MODERATE": (theme.YELLOW, "triangle-alert"),
           "HIGH": (theme.RED, "triangle-alert")}


class MainWindow(QMainWindow):
    def __init__(self, store):
        super().__init__()
        self.setWindowTitle(f"{theme.APP_NAME.title()} - Traffic Intelligence System")
        avail = QGuiApplication.primaryScreen().availableGeometry()      # the usable part of the screen
        self.resize(min(1366, avail.width()), min(820, avail.height()))
        self.setMinimumSize(820, 500)
        self.unread, self.level = 0, -1
        self.store = store

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self.build_header())

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        outer.addLayout(body, 1)

        # ---- sidebar
        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(214)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(0, 14, 0, 14)
        sl.setSpacing(2)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons = []
        for i, (name, icon_name) in enumerate(NAV):
            b = QPushButton("  " + name.replace("&", "&&"))      # && shows a real & (a single & is a shortcut marker)
            b.setObjectName("navButton")
            b.setCheckable(True)
            b.setIcon(icons.icon_states(icon_name, theme.DIM, "#FFFFFF", 20))
            b.setIconSize(QSize(20, 20))
            b.setCursor(Qt.PointingHandCursor)
            self.group.addButton(b, i)
            self.buttons.append(b)
            sl.addWidget(b)
        self.nav_names = [n for n, _i in NAV]
        self.side = side
        sl.addStretch(1)
        self.status_box = self.build_status_box()
        sl.addWidget(self.status_box)
        body.addWidget(side)

        # ---- screens
        self.stack = QStackedWidget()
        self.overview = OverviewPage(store)
        self.live = LiveMonitorPage(store)
        self.video_analysis = VideoAnalysisPage(store)
        self.risk_events = RiskEventsPage(store)
        self.priority_zones = PriorityZonesPage(store)
        self.reports_settings = ReportsSettingsPage(store)

        self.pages = [self.overview, self.live, self.video_analysis,
                      self.risk_events, self.priority_zones, self.reports_settings]
        for page in self.pages:
            self.stack.addWidget(self.scrollable(page))
        body.addWidget(self.stack, 1)

        self.live.event_clicked.connect(self.show_event)
        self.video_analysis.inspect_requested.connect(lambda: self.buttons[3].click())
        self.risk_events.session_requested.connect(self.load_session)
        self.group.idClicked.connect(self.stack.setCurrentIndex)
        self.buttons[0].setChecked(True)
        store.event_added.connect(self.on_event)
        store.traffic_changed.connect(self.set_traffic)
        store.cleared.connect(self.clear_bell)
        self.set_traffic(store.traffic)

    def show_event(self, event_id):
        """Open an event (clicked in the Live timeline) on the Risk Events screen."""
        self.buttons[3].click()
        self.pages[3].select_event(event_id)

    def load_session(self, sid):
        """Open a saved run on all screens."""
        if self.live.worker is not None and self.live.worker.isRunning():
            QMessageBox.information(self, "Analysis running", "Stop the current analysis before opening a saved run.")
            self.pages[3].refresh_sessions()
            return
        self.store.load_session(sid)

    @staticmethod
    def scrollable(page):
        """Wrap a screen so it scrolls instead of being cut off when the window is too small."""
        page.setObjectName("page")
        page.setStyleSheet("#page { background: transparent; }")
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.NoFrame)
        area.viewport().setObjectName("scrollViewport")
        area.viewport().setStyleSheet("#scrollViewport { background: transparent; }")      # only this widget, not its children
        area.setWidget(page)
        return area

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w, h = self.width(), self.height()
        level = 0 if w >= 1300 else (1 if w >= 1100 else 2)          # by width: sidebar and side panels
        short, xshort = h < 740, h < 600                             # by height: vertical space
        if (level, short, xshort) != self.level:
            self.apply_level(level, short, xshort)

    def apply_level(self, level, short, xshort):
        """Shrink the layout for small screens. level: 0 roomy, 1 compact, 2 narrow (by width);
        short / xshort: the window is not tall (by height)."""
        self.level = (level, short, xshort)
        v = 2 if xshort else (1 if short else 0)                     # vertical size step
        self.title_label.setFont(theme.heading_font((30, 26, 22)[v]))
        self.subtitle_label.setVisible(level < 2 and not xshort)
        self.tbox.setFixedSize((220, 200, 180)[level], (68, 56, 50)[v])
        self.bell_box.setFixedSize((92, 80, 64)[level], (68, 56, 50)[v])
        self.badge.move(self.bell_box.width() - 38, 6)
        self.header_lay.activate()                                   # the header is as tall as its content needs, never clipped
        self.header.setFixedHeight(max((84, 66, 54)[v], self.header_lay.sizeHint().height()))
        self.side.setFixedWidth((214, 176, 62)[level])
        self.status_box.setVisible(level < 2 and not xshort)
        for b, name in zip(self.buttons, self.nav_names):
            b.setText("" if level == 2 else "  " + name.replace("&", "&&"))
            b.setToolTip(name if level == 2 else "")
        for page in self.pages:
            if hasattr(page, "set_level"):
                page.set_level(level, short)

    def build_status_box(self):
        box = QFrame()
        box.setObjectName("statusBox")
        lay = QHBoxLayout(box)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(10)
        dot = QLabel()
        dot.setFixedSize(10, 10)
        dot.setStyleSheet(f"background: {theme.GREEN}; border-radius: 5px;")
        col = QVBoxLayout()
        col.setSpacing(0)
        a = QLabel("SYSTEM STATUS")
        a.setObjectName("cardLabel")
        b = QLabel("OPERATIONAL")
        b.setStyleSheet(f"color: {theme.GREEN}; {theme.STRONG_CSS} font-size: 12px;")
        col.addWidget(a)
        col.addWidget(b)
        lay.addWidget(dot)
        lay.addLayout(col, 1)
        wrap = QWidget()
        wl = QVBoxLayout(wrap)
        wl.setContentsMargins(12, 0, 12, 0)
        wl.addWidget(box)
        return wrap

    def closeEvent(self, event):
        """Stop the background analysis before the window closes."""
        self.live.stop()
        super().closeEvent(event)

    def build_header(self):
        h = self.header = QFrame()
        h.setObjectName("header")
        h.setFixedHeight(84)
        lay = self.header_lay = QHBoxLayout(h)
        lay.setContentsMargins(22, 6, 22, 6)
        lay.setSpacing(16)

        logo = QLabel()
        logo.setPixmap(icons.pixmap("shield-check", theme.ACCENT, 44, 1.6))
        lay.addWidget(logo)
        divider = QFrame()
        divider.setFixedSize(1, 46)
        divider.setStyleSheet(f"background: {theme.BORDER};")
        lay.addWidget(divider)

        col = QVBoxLayout()
        col.setSpacing(3)
        title = self.title_label = QLabel(theme.APP_NAME)
        title.setFont(theme.heading_font(32))
        title.setStyleSheet("color: white; letter-spacing: 0.5px;")
        sub = self.subtitle_label = QLabel(theme.APP_SUBTITLE)
        sub.setObjectName("subtitle")
        col.addWidget(title)
        col.addWidget(sub)
        lay.addLayout(col, 1)

        tbox = self.tbox = QFrame()
        tbox.setObjectName("headerBox")
        tbox.setFixedSize(220, 68)
        tl = QVBoxLayout(tbox)
        tl.setContentsMargins(12, 6, 12, 8)
        tl.setSpacing(3)
        cap = QLabel("TRAFFIC STATUS")
        cap.setObjectName("cardLabel")
        self.traffic_pill = QFrame()
        self.traffic_pill.setObjectName("trafficPill")
        pl = QHBoxLayout(self.traffic_pill)
        pl.setContentsMargins(10, 2, 10, 2)
        pl.setSpacing(8)
        self.traffic_icon = QLabel()
        self.traffic_text = QLabel()
        pl.addWidget(self.traffic_icon)
        pl.addWidget(self.traffic_text, 1)
        tl.addWidget(cap)
        tl.addWidget(self.traffic_pill)
        lay.addWidget(tbox)

        self.bell_box = QFrame()
        self.bell_box.setObjectName("headerBox")
        self.bell_box.setFixedSize(92, 68)
        bl = QHBoxLayout(self.bell_box)
        self.bell = QPushButton()
        self.bell.setObjectName("bell")
        self.bell.setIcon(icons.icon("bell", "#FFFFFF", 26))
        self.bell.setIconSize(QSize(26, 26))
        self.bell.setCursor(Qt.PointingHandCursor)
        self.bell.setToolTip("New high-severity alerts. Click to clear.")
        self.bell.clicked.connect(self.clear_bell)
        bl.addWidget(self.bell, 0, Qt.AlignCenter)
        self.badge = QLabel("0", self.bell_box)
        self.badge.setAlignment(Qt.AlignCenter)
        self.badge.setStyleSheet(f"background: {theme.RED}; color: white; border-radius: 10px; {theme.STRONG_CSS} font-size: 11px; padding: 0 5px;")
        self.badge.setFixedHeight(20)
        self.badge.setMinimumWidth(20)
        self.badge.move(54, 8)
        self.badge.hide()
        lay.addWidget(self.bell_box)
        return h

    def set_traffic(self, level):
        color, icon_name = TRAFFIC.get(level, (theme.BLUE, "activity"))
        self.traffic_icon.setPixmap(icons.pixmap(icon_name, color, 18))
        self.traffic_text.setText(level)
        self.traffic_text.setStyleSheet(f"color: {color}; {theme.STRONG_CSS} font-size: 15px;")
        self.traffic_pill.setStyleSheet(f"#trafficPill {{ background: {theme.rgba(color, 55)}; border: 1px solid {theme.rgba(color, 140)}; border-radius: 8px; }}")

    def on_event(self, ev):
        if ev["severity"] in ("HIGH", "CRITICAL"):
            self.unread += 1
            self.badge.setText(str(self.unread) if self.unread < 100 else "99+")
            self.badge.adjustSize()
            self.badge.show()

    def clear_bell(self):
        self.unread = 0
        self.badge.hide()
