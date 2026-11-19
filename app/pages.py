"""The screens. Overview and Risk Events are working; the rest are placeholders for later weeks."""
import html
import os
from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (QWidget, QGridLayout, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
                               QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QPushButton, QFrame, QBoxLayout)
import theme
import icons
from fake_data import EVENT_INFO
from widgets import (Panel, StatCard, AlertFeed, PipelineStrip, SampleHeatmap, HeatLegend, LineChart, DonutChart,
                     EVENT_ICON, event_color, event_seconds, make_pill, ProximityDiagramWidget)

CARDS = [("vehicles", "Vehicles", "car"), ("pedestrians", "Pedestrians", "person-standing"),
         ("near_misses", "Near Misses", "car-front"), ("sudden_braking", "Sudden Braking", "octagon-alert"),
         ("wrong_side", "Wrong-Side", "circle-plus"), ("restricted_entry", "Restricted Entry", "ban"),
         ("emergency_vehicles", "Emergency Vehicles", "siren"), ("high_risk", "High-Risk Events", "triangle-alert")]
STATUS_COLOR = {"NEW": theme.BLUE, "ACKNOWLEDGED": theme.YELLOW, "INVESTIGATING": theme.PURPLE, "RESOLVED": theme.GREEN}


def page_title(text, subtitle):
    """Big page title with a dim line under it."""
    box = QVBoxLayout()
    box.setSpacing(2)
    t = QLabel(text.upper())
    t.setFont(theme.heading_font(30))
    t.setStyleSheet("color: white; letter-spacing: 0.5px;")
    s = QLabel(subtitle)
    s.setObjectName("dim")
    box.addWidget(t)
    box.addWidget(s)
    box.sub_label = s                  # so a screen can hide it on short windows
    return box


def build_series(events, buckets=12):
    """Events per time slice (by video time), for the line chart: high risk, medium, info/low."""
    groups = {"High risk": [theme.RED, [0] * buckets], "Medium": [theme.YELLOW, [0] * buckets],
              "Info / low": [theme.BLUE, [0] * buckets]}
    if events:
        times = [event_seconds(e) for e in events]
        t0, span = min(times), max(max(times) - min(times), 1)
        for e, t in zip(events, times):
            key = "High risk" if e["severity"] in ("HIGH", "CRITICAL") else ("Medium" if e["severity"] == "MEDIUM" else "Info / low")
            groups[key][1][min(buckets - 1, int((t - t0) / span * buckets))] += 1
    return [(name, c, v) for name, (c, v) in groups.items()]


def severity_mix(events):
    """Counts for the donut: normal (info/low), high risk, medium."""
    hi = sum(e["severity"] in ("HIGH", "CRITICAL") for e in events)
    med = sum(e["severity"] == "MEDIUM" for e in events)
    return [("Info / low", theme.GREEN, len(events) - hi - med), ("High risk", theme.RED, hi), ("Medium", theme.YELLOW, med)]


class OverviewPage(QWidget):
    def __init__(self, store):
        super().__init__()
        self.store = store
        outer = QHBoxLayout(self)
        outer.setContentsMargins(18, 16, 18, 16)
        outer.setSpacing(14)
        left = QVBoxLayout()
        left.setSpacing(14)

        grid = QGridLayout()
        grid.setSpacing(12)
        self.cards = {}
        for i, (key, label, icon_name) in enumerate(CARDS):
            card = StatCard(label, theme.KPI[key], icon_name)
            self.cards[key] = card
            grid.addWidget(card, i // 4, i % 4)
        left.addLayout(grid)

        mid = QHBoxLayout()
        mid.setSpacing(14)
        heat = Panel("Risk Heatmap", right_icon="map-pin")
        stack = QGridLayout()
        stack.addWidget(SampleHeatmap(), 0, 0)
        stack.addWidget(HeatLegend(), 0, 0, Qt.AlignLeft | Qt.AlignBottom)
        stack.setContentsMargins(0, 0, 0, 0)
        heat.body.addLayout(stack, 1)
        mid.addWidget(heat, 5)

        right = QVBoxLayout()
        right.setSpacing(14)
        cp = Panel("Events Over Time")
        self.chart = LineChart()
        cp.body.addWidget(self.chart, 1)
        dp = Panel("Severity Mix")
        self.donut = DonutChart()
        dp.body.addWidget(self.donut, 1)
        right.addWidget(cp, 5)
        right.addWidget(dp, 3)
        mid.addLayout(right, 4)
        left.addLayout(mid, 1)
        self.pipeline = PipelineStrip()
        left.addWidget(self.pipeline)
        outer.addLayout(left, 1)

        self.feed = AlertFeed()
        self.feed.setFixedWidth(330)
        outer.addWidget(self.feed)

        for ev in reversed(store.events):
            self.feed.add_event(ev)
        self.update_counters(store.counters)
        self.refresh_charts()
        store.event_added.connect(self.feed.add_event)
        store.event_added.connect(lambda _e: self.refresh_charts())
        store.counters_changed.connect(self.update_counters)
        store.cleared.connect(self.feed.clear)
        store.cleared.connect(self.refresh_charts)

    def set_level(self, level, short):
        """level 0/1/2 = window width (roomy, compact, narrow); short = window is not tall."""
        for card in self.cards.values():
            card.set_compact(level >= 1 or short)
        self.pipeline.setVisible(not short)
        self.feed.setFixedWidth((330, 305, 280)[level])

    def update_counters(self, counters):
        for key, card in self.cards.items():
            card.set_value(counters[key])

    def refresh_charts(self):
        self.chart.set_series(build_series(self.store.events))
        self.donut.set_data(severity_mix(self.store.events))


class RiskEventsPage(QWidget):
    session_requested = Signal(int)      # the user picked a saved run
    COLUMNS = ["Event Type", "Object IDs", "Time ↓", "Zone", "Severity", "Status"]
    PAGE_SIZE = 10

    def __init__(self, store):
        super().__init__()
        self.store, self.selected, self.page = store, None, 0
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)
        head = page_title("Risk Events", "Near misses, unsafe manoeuvres, and safety-critical interactions")
        self.sub_label = head.sub_label
        root.addLayout(head)

        bar = QHBoxLayout()
        bar.setSpacing(10)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search events")
        
        self.date_btn = QPushButton("  2025-05-23")
        self.date_btn.setObjectName("ghost")
        self.date_btn.setIcon(icons.icon("calendar", "#FFFFFF", 15))
        self.date_btn.setFixedWidth(130)

        self.zone_filter = QComboBox()
        self.zone_filter.addItems(["All Zones", "Zone 1", "Zone 2", "Zone 3", "Zone 4"])
        self.zone_filter.setFixedWidth(120)

        self.session_box = QComboBox()
        self.session_box.setMinimumWidth(180)
        self.sev = QComboBox()
        self.sev.addItems(["All Severities", "CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"])
        self.stat = QComboBox()
        self.stat.addItems(["All Status", "NEW", "ACKNOWLEDGED", "INVESTIGATING", "RESOLVED"])
        clear = QPushButton("  CLEAR FILTERS")
        clear.setObjectName("ghost")
        clear.setIcon(icons.icon("refresh-cw", "#FFFFFF", 16))
        
        bar.addWidget(self.search, 1)
        bar.addWidget(self.date_btn)
        bar.addWidget(self.zone_filter)
        bar.addWidget(self.session_box)
        bar.addWidget(self.sev)
        bar.addWidget(self.stat)
        bar.addWidget(clear)
        root.addLayout(bar)

        main = QHBoxLayout()
        main.setSpacing(14)
        
        # Left side: Events Table + Safety Interaction Diagram
        left_side = QVBoxLayout()
        left_side.setSpacing(12)

        tp = Panel("")
        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setShowGrid(False)
        self.table.setIconSize(QSize(18, 18))
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.Stretch)
        for col in (0, 1, 2):
            hh.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        for col, width in ((4, 112), (5, 150)):                 # pill columns need a fixed width
            hh.setSectionResizeMode(col, QHeaderView.Fixed)
            self.table.setColumnWidth(col, width)
        tp.body.addWidget(self.table, 1)
        pager = QHBoxLayout()
        self.prev = QPushButton()
        self.prev.setObjectName("ghost")
        self.prev.setIcon(icons.icon("chevron-left", "#FFFFFF", 16))
        self.next = QPushButton()
        self.next.setObjectName("ghost")
        self.next.setIcon(icons.icon("chevron-right", "#FFFFFF", 16))
        self.page_label = QLabel("")
        self.page_label.setObjectName("dim")
        pager.addWidget(self.page_label)
        pager.addStretch(1)
        pager.addWidget(self.prev)
        pager.addWidget(self.next)
        tp.body.addLayout(pager)
        left_side.addWidget(tp, 1)

        # Proximity interaction diagram (matching Page 4)
        diag_panel = Panel("Safety-Critical Proximity Interaction")
        self.prox_diag = ProximityDiagramWidget()
        diag_panel.body.addWidget(self.prox_diag)
        left_side.addWidget(diag_panel)

        main.addLayout(left_side, 1)

        dp = self.details_panel = Panel("Selected Event Details")
        dp.setFixedWidth(340)
        head = QHBoxLayout()
        self.type_icon = QLabel()
        self.type_icon.setFixedSize(44, 44)
        self.type_icon.setAlignment(Qt.AlignCenter)
        self.title = QLabel("Select an event")
        self.title.setFont(theme.heading_font(21))
        self.title.setWordWrap(True)
        head.addWidget(self.type_icon)
        head.addWidget(self.title, 1)
        dp.body.addLayout(head)
        self.badge_row = QHBoxLayout()
        dp.body.addLayout(self.badge_row)
        self.snap = QLabel()                     # picture of the moment, saved when the event happened
        self.snap.setAlignment(Qt.AlignCenter)
        self.snap.setStyleSheet(f"background: #03070F; border: 1px solid {theme.BORDER}; border-radius: 8px;")
        self.snap.hide()
        dp.body.addWidget(self.snap)

        # Mini viewer controls under snapshot
        snap_ctrls = QHBoxLayout()
        snap_ctrls.setSpacing(6)
        snap_ctrls.setAlignment(Qt.AlignCenter)
        for ic_name in ["play", "x", "maximize", "locate"]:
            mb = QPushButton()
            mb.setObjectName("ghost")
            mb.setFixedSize(28, 28)
            mb.setIcon(icons.icon(ic_name, "#FFFFFF", 14))
            snap_ctrls.addWidget(mb)
        dp.body.addLayout(snap_ctrls)

        self.info = QGridLayout()
        self.info.setHorizontalSpacing(10)
        self.info.setVerticalSpacing(10)
        self.info_values = {}
        for r, (key, label, icon_name) in enumerate([("objects", "Objects", "users"), ("zone", "Zone", "map-pin"),
                                                    ("time", "Video time", "clock-3"), ("details", "Details", "activity"),
                                                    ("status", "Status", "flag")]):
            ic = QLabel()
            ic.setPixmap(icons.pixmap(icon_name, theme.CYAN, 16))
            lab = QLabel(label)
            lab.setObjectName("dim")
            val = QLabel("")
            val.setWordWrap(True)
            self.info.addWidget(ic, r, 0)
            self.info.addWidget(lab, r, 1)
            self.info.addWidget(val, r, 2)
            self.info_values[key] = val
        self.info.setColumnStretch(2, 1)
        dp.body.addLayout(self.info)
        dp.body.addStretch(1)
        
        self.btn_ack = QPushButton("  Acknowledge")
        self.btn_ack.setObjectName("danger")
        self.btn_ack.setIcon(icons.icon("check", "#FFFFFF", 16))
        self.btn_inv = QPushButton("  Investigate")
        self.btn_inv.setObjectName("primary")
        self.btn_inv.setIcon(icons.icon("search", "#FFFFFF", 16))
        
        self.btn_dl = QPushButton()
        self.btn_dl.setObjectName("ghost")
        self.btn_dl.setIcon(icons.icon("download", "#FFFFFF", 16))
        self.btn_dl.setFixedSize(38, 36)
        self.btn_dl.setToolTip("Export snapshot")

        self.btn_res = QPushButton("  Resolve")
        self.btn_res.setObjectName("ghost")
        self.btn_res.setIcon(icons.icon("circle-check", "#FFFFFF", 16))
        
        top = self.btn_row = QBoxLayout(QBoxLayout.LeftToRight)
        top.setSpacing(8)
        top.addWidget(self.btn_ack)
        top.addWidget(self.btn_inv)
        dp.body.addLayout(top)

        bot = QHBoxLayout()
        bot.setSpacing(8)
        bot.addWidget(self.btn_dl)
        bot.addWidget(self.btn_res, 1)
        dp.body.addLayout(bot)

        main.addWidget(dp)
        root.addLayout(main, 1)

        self.search.textChanged.connect(self.filters_changed)
        self.zone_filter.currentIndexChanged.connect(self.filters_changed)
        self.sev.currentIndexChanged.connect(self.filters_changed)
        self.stat.currentIndexChanged.connect(self.filters_changed)
        clear.clicked.connect(self.clear_filters)
        self.prev.clicked.connect(lambda: self.go_page(-1))
        self.next.clicked.connect(lambda: self.go_page(1))
        self.table.itemSelectionChanged.connect(self.on_select)
        self.btn_ack.clicked.connect(lambda: self.set_status("ACKNOWLEDGED"))
        self.btn_inv.clicked.connect(lambda: self.set_status("INVESTIGATING"))
        self.btn_res.clicked.connect(lambda: self.set_status("RESOLVED"))
        store.event_added.connect(lambda _e: self.refresh())
        store.event_changed.connect(lambda _e: self.refresh())
        store.cleared.connect(self.on_cleared)
        store.sessions_changed.connect(self.refresh_sessions)
        self.session_box.activated.connect(self.on_session_chosen)
        self.shown = []
        self.refresh_sessions()
        self.refresh()

    def set_level(self, level, short):
        self.details_panel.setFixedWidth((340, 300, 260)[level])
        self.table.verticalHeader().setDefaultSectionSize(36 if short else 44)
        self.sub_label.setVisible(not short)
        self.snap.setMaximumHeight(110 if short else 170)
        self.btn_row.setDirection(QBoxLayout.LeftToRight if level == 0 else QBoxLayout.TopToBottom)   # narrow panel: stack the buttons
        self.show_details()

    def refresh_sessions(self):
        """Fill the Saved runs menu from the database."""
        box, db = self.session_box, self.store.db
        box.blockSignals(True)
        box.clear()
        runs = db.sessions() if db else []
        box.addItem("Saved runs" if runs else "Saved runs (none yet)")
        for s in runs:
            box.addItem(f"{s['started']}  |  {s['source']}  ({s['n_events']} events)", s["id"])
        for i in range(1, box.count()):
            if box.itemData(i) == self.store.active_session:
                box.setCurrentIndex(i)
        box.blockSignals(False)

    def on_session_chosen(self, index):
        if index > 0:
            self.session_requested.emit(self.session_box.itemData(index))

    def select_event(self, event_id):
        """Jump to one event (from the Live timeline): clear filters, find its page, select it."""
        self.search.clear()
        self.sev.setCurrentIndex(0)
        self.stat.setCurrentIndex(0)
        self.selected = event_id
        allm = [e for e in self.store.events if self.matches(e)]
        self.page = next((i for i, e in enumerate(allm) if e["event_id"] == event_id), 0) // self.PAGE_SIZE
        self.refresh()

    def on_cleared(self):
        self.selected, self.page = None, 0
        self.refresh()

    def filters_changed(self):
        self.page = 0
        self.refresh()

    def clear_filters(self):
        self.search.clear()
        self.zone_filter.setCurrentIndex(0)
        self.sev.setCurrentIndex(0)
        self.stat.setCurrentIndex(0)

    def go_page(self, delta):
        self.page += delta
        self.refresh()

    def matches(self, ev):
        q = self.search.text().strip().lower()
        if q and q not in f"{ev['type']} {ev['objects']} {ev['zone']}".lower():
            return False
        if self.zone_filter.currentIndex() and ev["zone"] != self.zone_filter.currentText():
            return False
        if self.sev.currentIndex() and ev["severity"] != self.sev.currentText():
            return False
        if self.stat.currentIndex() and ev["status"] != self.stat.currentText():
            return False
        return True

    @staticmethod
    def pill_cell(text, color):
        """A pill centered in a table cell."""
        box = QWidget()
        lay = QHBoxLayout(box)
        lay.setContentsMargins(4, 0, 4, 0)
        lay.addWidget(make_pill(text, color), 0, Qt.AlignCenter)
        return box

    def refresh(self):
        """Rebuild the table from the store (keeps the selected event selected)."""
        allm = [e for e in self.store.events if self.matches(e)]
        pages = max(1, -(-len(allm) // self.PAGE_SIZE))
        self.page = max(0, min(self.page, pages - 1))
        self.shown = allm[self.page * self.PAGE_SIZE:(self.page + 1) * self.PAGE_SIZE]
        self.page_label.setText(f"{len(allm)} events   |   page {self.page + 1} of {pages}")
        self.prev.setEnabled(self.page > 0)
        self.next.setEnabled(self.page < pages - 1)
        self.table.blockSignals(True)
        self.table.clearContents()
        self.table.setRowCount(len(self.shown))
        for r, ev in enumerate(self.shown):
            kind = QTableWidgetItem(EVENT_INFO[ev["type"]][0].title())
            kind.setIcon(icons.icon(EVENT_ICON.get(ev["type"], "triangle-alert"), event_color(ev), 18))
            self.table.setItem(r, 0, kind)
            for c, text in ((1, ev["objects"]), (2, ev["time"]), (3, ev["zone"])):
                self.table.setItem(r, c, QTableWidgetItem(text))
            self.table.setCellWidget(r, 4, self.pill_cell(ev["severity"], theme.SEVERITY_COLOR[ev["severity"]]))
            self.table.setCellWidget(r, 5, self.pill_cell(ev["status"], STATUS_COLOR.get(ev["status"], theme.BLUE)))
            if self.selected == ev["event_id"]:
                self.table.selectRow(r)
        self.table.blockSignals(False)
        self.show_details()

    def on_select(self):
        rows = self.table.selectionModel().selectedRows()
        self.selected = self.shown[rows[0].row()]["event_id"] if rows else None
        self.show_details()

    def current(self):
        return next((e for e in self.store.events if e["event_id"] == self.selected), None)

    def show_details(self):
        ev = self.current()
        for b in (self.btn_ack, self.btn_inv, self.btn_res):
            b.setEnabled(ev is not None)
        while self.badge_row.count():
            item = self.badge_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not ev:
            self.type_icon.clear()
            self.type_icon.setStyleSheet("")
            self.title.setText("Select an event")
            for v in self.info_values.values():
                v.setText("")
            self.snap.hide()
            return
        col = event_color(ev)
        self.type_icon.setPixmap(icons.pixmap(EVENT_ICON.get(ev["type"], "triangle-alert"), col, 24))
        self.type_icon.setStyleSheet(f"background: {theme.rgba(col, 35)}; border-radius: 10px;")
        self.title.setText(EVENT_INFO[ev["type"]][0].title())
        path = self.store.db.snapshot_path(ev.get("snapshot")) if self.store.db else None
        pm = QPixmap(path) if path and os.path.exists(path) else QPixmap()
        if pm.isNull():
            self.snap.hide()
        else:
            self.snap.setPixmap(pm.scaled(self.details_panel.width() - 34, self.snap.maximumHeight(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.snap.show()
        self.badge_row.addWidget(make_pill(ev["severity"], theme.SEVERITY_COLOR[ev["severity"]], True), 0, Qt.AlignLeft)
        self.badge_row.addStretch(1)
        vals = {"objects": ev["objects"], "zone": ev["zone"], "time": ev["time"], "details": ev["details"] or "-", "status": ev["status"]}
        for key, text in vals.items():
            self.info_values[key].setText(html.escape(text))
            self.info_values[key].setStyleSheet(f"color: white; {theme.STRONG_CSS}")
        if hasattr(self, "prox_diag"):
            det = ev.get("details", "")
            d_str = "2.4 m"
            if "dist" in det.lower():
                import re
                m = re.search(r"(\d+(\.\d+)?\s*m)", det)
                if m:
                    d_str = m.group(1)
            self.prox_diag.set_distance(d_str)

    def set_status(self, status):
        if self.selected is not None:
            self.store.set_status(self.selected, status)


class PlaceholderPage(QWidget):
    """A screen that is planned but not built yet."""
    def __init__(self, title, subtitle, icon_name, week):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.addLayout(page_title(title, subtitle))
        box = Panel("")
        col = QVBoxLayout()
        col.setAlignment(Qt.AlignCenter)
        ic = QLabel()
        ic.setPixmap(icons.pixmap(icon_name, theme.CYAN, 56, 1.4))
        ic.setAlignment(Qt.AlignCenter)
        msg = QLabel(f"Planned for {week}")
        msg.setAlignment(Qt.AlignCenter)
        msg.setStyleSheet(f"color: {theme.DIM}; font-size: 14px; {theme.STRONG_CSS}")
        col.addWidget(ic)
        col.addWidget(msg)
        box.body.addStretch(1)
        box.body.addLayout(col)
        box.body.addStretch(1)
        lay.addWidget(box, 1)
