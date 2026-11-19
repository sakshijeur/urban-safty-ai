"""Reusable building blocks, styled like the design: panels, counter cards, alert feed, charts, pipeline strip."""
import math
import random
from PySide6.QtCore import Qt, QRectF, QPointF, QVariantAnimation, QEasingCurve
from PySide6.QtGui import (QPainter, QColor, QPen, QBrush, QPainterPath, QLinearGradient, QRadialGradient, QFont)
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QHBoxLayout, QScrollArea, QWidget, QSizePolicy
import theme
import icons
from fake_data import EVENT_INFO

# one icon per event type (used in the alert feed and the tables)
EVENT_ICON = {"NEAR_MISS": "car-front", "VEH_VEH_RISK": "car", "VEH_PED_RISK": "person-standing",
              "SUDDEN_BRAKE": "octagon-alert", "LANE_CHANGE": "route", "WRONG_SIDE": "circle-plus",
              "CONGESTION": "activity", "EMERGENCY_VEH": "ambulance", "RESTRICTED_ENTRY": "ban",
              "POSSIBLE_COLLISION": "triangle-alert"}


def event_color(ev):
    """Restricted-zone events are purple, emergency vehicles blue, everything else follows severity."""
    if ev["type"] == "RESTRICTED_ENTRY":
        return theme.PURPLE
    if ev["type"] == "EMERGENCY_VEH":
        return theme.BLUE
    return theme.SEVERITY_COLOR.get(ev["severity"], theme.BLUE)


def tile_color(ev):
    """Color of the square icon tile in the alert feed."""
    if ev["type"] == "RESTRICTED_ENTRY":
        return theme.TILE["purple"]
    if ev["type"] == "EMERGENCY_VEH":
        return theme.TILE["green"]
    return {"CRITICAL": theme.TILE["red"], "HIGH": theme.TILE["red"], "MEDIUM": theme.TILE["amber"],
            "LOW": theme.TILE["green"], "INFO": theme.TILE["blue"]}.get(ev["severity"], theme.TILE["blue"])


def event_seconds(ev):
    """Video time of an event in seconds (from its HH:MM:SS text)."""
    try:
        h, m, s = (int(x) for x in ev["time"].split(":"))
        return h * 3600 + m * 60 + s
    except ValueError:
        return 0


def make_pill(text, color, filled=False):
    """A small rounded colored label (severity / status)."""
    lab = QLabel(text)
    lab.setAlignment(Qt.AlignCenter)
    lab.setStyleSheet(theme.pill_style(color, filled))
    return lab


class Panel(QFrame):
    """A rounded dark box with an optional title and an optional small icon at the top right."""
    def __init__(self, title="", right_icon=None):
        super().__init__()
        self.setObjectName("panel")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(16, 14, 16, 14)
        self.body.setSpacing(10)
        if title or right_icon:
            head = QHBoxLayout()
            t = QLabel(title.upper())
            t.setObjectName("panelTitle")
            head.addWidget(t)
            head.addStretch(1)
            if right_icon:
                ic = QLabel()
                ic.setPixmap(icons.pixmap(right_icon, theme.CYAN, 16))
                head.addWidget(ic)
            self.body.addLayout(head)


class StatCard(QFrame):
    """A counter: colored icon on the left, small label and a big white number. The number counts up smoothly."""
    def __init__(self, label, color, icon_name, compact=False):
        super().__init__()
        self.setObjectName("card")
        lay = QHBoxLayout(self)
        self._lay, self._icon_name, self._color = lay, icon_name, color
        ic = QLabel()
        ic.setAlignment(Qt.AlignCenter)
        self._ic = ic
        col = QVBoxLayout()
        col.setSpacing(0)
        self.label = QLabel(label.upper())
        self.label.setObjectName("cardLabel")
        self.label.setWordWrap(True)
        self.value = QLabel("0")
        self.value.setStyleSheet("color: white; background: transparent;")
        col.addWidget(self.label)
        col.addWidget(self.value)
        lay.addWidget(ic)
        lay.addLayout(col, 1)
        self._shown = 0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(450)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(lambda v: self.value.setText(str(int(v))))
        self.set_compact(compact)

    def set_compact(self, compact):
        """Smaller icon, margins and number for small screens."""
        size, px = (34, 17) if compact else (48, 26)
        self._lay.setContentsMargins(*((10, 5, 10, 5) if compact else (14, 10, 14, 10)))
        self._lay.setSpacing(9 if compact else 14)
        self._ic.setFixedSize(size, size)
        self._ic.setPixmap(icons.pixmap(self._icon_name, self._color, px))
        self._ic.setStyleSheet(f"background: {theme.rgba(self._color, 30)}; border-radius: {size // 2}px;")
        self.value.setFont(theme.heading_font(24 if compact else 36))

    def set_value(self, v):
        if isinstance(v, int) and abs(v - self._shown) > 1 and self.isVisible():
            self._anim.stop()
            self._anim.setStartValue(self._shown)
            self._anim.setEndValue(v)
            self._anim.start()
        else:
            self.value.setText(str(v))
        self._shown = v if isinstance(v, int) else 0


class AlertRow(QFrame):
    """One line in the alert feed: colored icon tile, title, location line, time."""
    def __init__(self, ev):
        super().__init__()
        self.setObjectName("alertRow")
        self.setStyleSheet(f"#alertRow {{ background: {theme.ROW}; border: 1px solid {theme.ROW_BORDER}; border-radius: 8px; }}"
                           f"#alertRow:hover {{ border: 1px solid {theme.BORDER_HI}; }}")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 7, 8, 7)
        lay.setSpacing(9)
        color = tile_color(ev)
        tile = QLabel()
        tile.setFixedSize(36, 36)
        tile.setAlignment(Qt.AlignCenter)
        tile.setPixmap(icons.pixmap(EVENT_ICON.get(ev["type"], "triangle-alert"), "#FFFFFF", 20))
        tile.setStyleSheet(f"background: {color}; border-radius: 8px;")
        col = QVBoxLayout()
        col.setSpacing(3)
        title = QLabel(EVENT_INFO[ev["type"]][0].title())
        title.setStyleSheet(f"{theme.STRONG_CSS} font-size: 12px; color: white;")
        sub = QHBoxLayout()
        sub.setSpacing(5)
        pin = QLabel()
        pin.setPixmap(icons.pixmap("map-pin", event_color(ev), 12))
        where = QLabel(ev["objects"])
        where.setStyleSheet(f"color: {theme.DIM}; font-size: 11px;")
        where.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        sub.addWidget(pin)
        sub.addWidget(where, 1)
        col.addWidget(title)
        col.addLayout(sub)
        t = QLabel(ev["time"])
        t.setStyleSheet(f"color: white; font-size: 11px; {theme.STRONG_CSS}")
        z = QLabel(ev["zone"])
        z.setStyleSheet(f"color: {theme.DIM}; font-size: 11px;")
        right = QVBoxLayout()
        right.setSpacing(3)
        right.addWidget(t, 0, Qt.AlignRight)
        right.addWidget(z, 0, Qt.AlignRight)
        lay.addWidget(tile)
        lay.addLayout(col, 1)
        lay.addLayout(right)


class AlertFeed(Panel):
    """Scrolling list of the newest alerts (newest on top)."""
    MAX_ROWS = 30

    def __init__(self):
        super().__init__("Alert Feed", right_icon="funnel")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setObjectName("feedInner")
        inner.setStyleSheet("#feedInner { background: transparent; }")
        scroll.viewport().setObjectName("feedViewport")
        scroll.viewport().setStyleSheet("#feedViewport { background: transparent; }")
        self.rows = QVBoxLayout(inner)
        self.rows.setContentsMargins(0, 0, 4, 0)
        self.rows.setSpacing(8)
        self.empty = QLabel("No alerts yet")
        self.empty.setObjectName("dim")
        self.empty.setAlignment(Qt.AlignCenter)
        self.rows.addWidget(self.empty)
        self.rows.addStretch(1)
        scroll.setWidget(inner)
        self.body.addWidget(scroll, 1)
        self.count = 0

    def clear(self):
        """Remove all alerts (a new analysis is starting)."""
        while self.rows.count() > 2:
            item = self.rows.takeAt(0)
            item.widget().deleteLater()
        self.count = 0
        self.empty.show()

    def add_event(self, ev):
        self.empty.hide()
        self.rows.insertWidget(0, AlertRow(ev))
        self.count += 1
        while self.count > self.MAX_ROWS:
            item = self.rows.takeAt(self.rows.count() - 3)
            item.widget().deleteLater()
            self.count -= 1


class PipelineStrip(Panel):
    """The five steps of the system with dashed arrows and a green check under each."""
    STEPS = [("video", "VIDEO"), ("brain-circuit", "DETECT"), ("crosshair", "TRACK"),
             ("shield-check", "RULES"), ("bell", "ALERTS")]

    def __init__(self):
        super().__init__("")
        self.canvas = _PipelineCanvas(self.STEPS)
        self.body.addWidget(self.canvas)


class _PipelineCanvas(QWidget):
    def __init__(self, steps):
        super().__init__()
        self.steps = steps
        self.setMinimumHeight(108)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, n = self.width(), len(self.steps)
        cy, r = 36, 27
        xs = [w * (i + 0.5) / n for i in range(n)]
        for i in range(n - 1):                                    # dashed arrows between circles
            x0, x1 = xs[i] + r + 12, xs[i + 1] - r - 12
            pen = QPen(QColor(theme.CYAN), 1.6, Qt.DashLine)
            p.setPen(pen)
            p.drawLine(QPointF(x0, cy), QPointF(x1 - 6, cy))
            p.setPen(QPen(QColor(theme.CYAN), 1.8))
            p.drawLine(QPointF(x1 - 7, cy - 5), QPointF(x1, cy))
            p.drawLine(QPointF(x1 - 7, cy + 5), QPointF(x1, cy))
        for (name, label), x in zip(self.steps, xs):
            g = QRadialGradient(QPointF(x, cy), r)
            g.setColorAt(0, theme.qcolor(theme.CYAN, 50))
            g.setColorAt(1, theme.qcolor(theme.CYAN, 8))
            p.setBrush(QBrush(g))
            p.setPen(QPen(QColor(theme.CYAN), 1.6))
            p.drawEllipse(QPointF(x, cy), r, r)
            pm = icons.pixmap(name, theme.BLUE, 28)
            p.drawPixmap(int(x - 14), int(cy - 14), pm)
            p.setPen(QColor(theme.DIM))
            f = p.font()
            f.setPointSize(8)
            f.setBold(True)
            p.setFont(f)
            p.drawText(QRectF(x - 40, cy + r + 6, 80, 14), Qt.AlignCenter, label)
            p.setBrush(QColor(theme.GREEN))                       # the green check
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(x, cy + r + 30), 8, 8)
            p.drawPixmap(int(x - 5), int(cy + r + 25), icons.pixmap("check", "#04210F", 10, 3))


class LineChart(QWidget):
    """Smooth multi-line chart with soft fills and point markers."""
    def __init__(self):
        super().__init__()
        self.series = []                      # [(name, color, [values])]
        self.setMinimumHeight(90)

    def set_series(self, series):
        self.series = series
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        plot = QRectF(34, 30, w - 34 - 12, h - 30 - 12)
        small = QFont(p.font())
        small.setPointSize(8)
        p.setFont(small)
        x = 34
        for name, color, _v in self.series:                      # legend
            p.setBrush(QColor(color))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(x + 4, 13), 4, 4)
            p.setPen(QColor(theme.DIM))
            tw = p.fontMetrics().horizontalAdvance(name)
            p.drawText(QPointF(x + 14, 17), name)
            x += tw + 34
        top = max([max(v) for _n, _c, v in self.series if v] + [1])
        top = max(4, int(math.ceil(top / 4.0)) * 4)             # 4 even grid steps with whole numbers
        for i in range(5):                                        # grid and y labels
            yv = top * i / 4
            y = plot.bottom() - plot.height() * i / 4
            p.setPen(QPen(QColor("#10233B"), 1))
            p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            p.setPen(QColor(theme.DIM))
            p.drawText(QRectF(0, y - 8, 28, 16), Qt.AlignRight | Qt.AlignVCenter, f"{yv:g}")
        if not any(any(v) for _n, _c, v in self.series):
            p.setPen(QColor(theme.DIM))
            p.drawText(plot, Qt.AlignCenter, "No events yet")
            return
        for name, color, vals in self.series:
            if len(vals) < 2:
                continue
            pts = [QPointF(plot.left() + plot.width() * i / (len(vals) - 1),
                           plot.bottom() - plot.height() * v / top) for i, v in enumerate(vals)]
            path = QPainterPath(pts[0])
            for i in range(len(pts) - 1):                         # smooth curve through the points
                p0, p1, p2 = pts[max(i - 1, 0)], pts[i], pts[i + 1]
                p3 = pts[min(i + 2, len(pts) - 1)]
                path.cubicTo(p1 + (p2 - p0) / 6, p2 - (p3 - p1) / 6, p2)
            fill = QPainterPath(path)
            fill.lineTo(pts[-1].x(), plot.bottom())
            fill.lineTo(pts[0].x(), plot.bottom())
            fill.closeSubpath()
            g = QLinearGradient(0, plot.top(), 0, plot.bottom())
            g.setColorAt(0, theme.qcolor(color, 70))
            g.setColorAt(1, theme.qcolor(color, 0))
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(g))
            p.drawPath(fill)
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(color), 2))
            p.drawPath(path)
            p.setBrush(QColor(color))
            p.setPen(QPen(QColor(theme.PANEL), 1.5))
            for pt in pts:
                p.drawEllipse(pt, 3, 3)


class DonutChart(QWidget):
    """Ring chart with a legend on the right."""
    def __init__(self):
        super().__init__()
        self.items = []                       # [(label, color, count)]
        self.setMinimumHeight(90)

    def set_data(self, items):
        self.items = items
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        side = min(self.height() - 8, self.width() * 0.5)
        ring = QRectF(8 + 8, (self.height() - side) / 2 + 8, side - 16, side - 16)
        total = sum(c for _l, _col, c in self.items)
        width = max(10, side * 0.11)
        p.setBrush(Qt.NoBrush)
        if total == 0:
            p.setPen(QPen(QColor("#13263D"), width))
            p.drawEllipse(ring)
        else:
            angle = 90 * 16
            for _label, color, count in self.items:
                if not count:
                    continue
                span = -int(360 * 16 * count / total)
                p.setPen(QPen(QColor(color), width, Qt.SolidLine, Qt.FlatCap))
                p.drawArc(ring, angle, span + (16 if span < -48 else 0))   # a hair of gap between slices
                angle += span
        p.setPen(QColor("white"))
        f = QFont(theme.heading_font(26))
        p.setFont(f)
        p.drawText(ring, Qt.AlignCenter, str(total))
        lx = 8 + side + 18
        small = QFont(p.font())
        small.setPointSize(9)
        small.setBold(False)
        p.setFont(small)
        y = max(10, (self.height() - 24 * len(self.items)) / 2)
        for label, color, count in self.items:
            p.setBrush(QColor(color))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(lx + 4, y + 10), 4.5, 4.5)
            p.setPen(QColor(theme.DIM))
            p.drawText(QPointF(lx + 16, y + 14), f"{label}")
            p.setPen(QColor("white"))
            p.drawText(QRectF(lx, y, self.width() - lx - 6, 20), Qt.AlignRight | Qt.AlignVCenter, str(count))
            y += 24


class SampleHeatmap(QWidget):
    """Interactive risk heatmap on an urban road network matching Page 1."""
    def __init__(self):
        super().__init__()
        rnd = random.Random(11)
        self.streets = []
        for _ in range(32):
            if rnd.random() < 0.5:
                y = rnd.uniform(0.0, 1.0)
                self.streets.append(((0.0, y), (1.0, y + rnd.uniform(-0.25, 0.25))))
            else:
                x = rnd.uniform(0.0, 1.0)
                self.streets.append(((x, 0.0), (x + rnd.uniform(-0.25, 0.25), 1.0)))
        self.hot = [
            ((0.08, 0.35), (0.62, 0.82), theme.RED),
            ((0.30, 0.15), (0.78, 0.92), "#FF8A1F"),
            ((0.05, 0.62), (0.55, 0.30), theme.YELLOW),
            ((0.55, 0.10), (0.95, 0.55), theme.GREEN),
            ((0.20, 0.70), (0.80, 0.30), theme.CYAN)
        ]
        self.setMinimumHeight(160)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(0, 0, w, h), 8, 8)
        p.setClipPath(clip)
        p.fillRect(self.rect(), QColor("#030814"))

        # Street grid
        for (x0, y0), (x1, y1) in self.streets:
            p.setPen(QPen(QColor("#0E1E34"), 1.6))
            p.drawLine(QPointF(x0 * w, y0 * h), QPointF(x1 * w, y1 * h))

        # Glowing thermal risk paths
        for (x0, y0), (x1, y1), color in self.hot:
            for width, alpha in ((22, 18), (12, 50), (4, 220)):
                p.setPen(QPen(theme.qcolor(color, alpha), width, Qt.SolidLine, Qt.RoundCap))
                p.drawLine(QPointF(x0 * w, y0 * h), QPointF(x1 * w, y1 * h))

        # 5 Status Indicator Dots on the left (matching Page 1)
        for i, col in enumerate([theme.RED, "#FF8A1F", theme.YELLOW, theme.GREEN, theme.CYAN]):
            p.setBrush(QColor(col))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(18, h * 0.45 + i * 16), 4.5, 4.5)

        # Map zoom controls on the right (matching Page 1)
        btn_x, btn_y = w - 34, h * 0.60
        p.setBrush(QColor(6, 18, 33, 210))
        p.setPen(QPen(QColor(theme.BORDER_HI), 1))
        p.drawRoundedRect(QRectF(btn_x, btn_y, 22, 46), 4, 4)
        p.setPen(QColor("white"))
        p.setFont(QFont("Segoe UI", 9, QFont.Bold))
        p.drawText(QRectF(btn_x, btn_y, 22, 22), Qt.AlignCenter, "+")
        p.setPen(QPen(QColor(theme.BORDER), 1))
        p.drawLine(QPointF(btn_x, btn_y + 23), QPointF(btn_x + 22, btn_y + 23))
        p.setPen(QColor("white"))
        p.drawText(QRectF(btn_x, btn_y + 23, 22, 22), Qt.AlignCenter, "-")

        # Compass crosshair icon above zoom
        p.drawPixmap(int(btn_x), int(btn_y - 28), icons.pixmap("locate", theme.CYAN, 18))


class ProximityDiagramWidget(QWidget):
    """Safety-Critical Interaction Diagram matching bottom of Page 4 (Car <-> Ped <-> Bike)."""
    def __init__(self):
        super().__init__()
        self.setFixedHeight(120)
        self.dist_text = "2.4 m"

    def set_distance(self, dist_str):
        self.dist_text = dist_str
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        p.fillRect(0, 0, w, h, QColor("#030814"))
        cy = h * 0.45
        r = 28

        # 3 node centers
        cx_car = w * 0.22
        cx_ped = w * 0.50
        cx_bike = w * 0.78

        # Connecting arrow between Car and Pedestrian
        p.setPen(QPen(QColor(theme.RED), 2))
        p.drawLine(QPointF(cx_car + r + 6, cy), QPointF(cx_ped - r - 6, cy))
        # Arrow heads
        p.drawLine(QPointF(cx_ped - r - 12, cy - 4), QPointF(cx_ped - r - 6, cy))
        p.drawLine(QPointF(cx_ped - r - 12, cy + 4), QPointF(cx_ped - r - 6, cy))
        p.drawLine(QPointF(cx_car + r + 12, cy - 4), QPointF(cx_car + r + 6, cy))
        p.drawLine(QPointF(cx_car + r + 12, cy + 4), QPointF(cx_car + r + 6, cy))

        # Connecting arrow between Bike and Pedestrian
        p.setPen(QPen(QColor(theme.GREEN), 2))
        p.drawLine(QPointF(cx_bike - r - 6, cy), QPointF(cx_ped + r + 6, cy))
        p.drawLine(QPointF(cx_ped + r + 12, cy - 4), QPointF(cx_ped + r + 6, cy))
        p.drawLine(QPointF(cx_ped + r + 12, cy + 4), QPointF(cx_ped + r + 6, cy))

        # Distance tag (2.4 m) in red
        tag_rect = QRectF(w * 0.42, h - 26, 68, 18)
        p.setPen(QColor("#FF4D4F"))
        p.setFont(QFont("Segoe UI", 9, QFont.Bold))
        p.drawText(tag_rect, Qt.AlignCenter, self.dist_text)

        # 1. Car Node (Red circle)
        g1 = QRadialGradient(QPointF(cx_car, cy), r)
        g1.setColorAt(0, theme.qcolor(theme.RED, 60))
        g1.setColorAt(1, theme.qcolor(theme.RED, 15))
        p.setBrush(QBrush(g1))
        p.setPen(QPen(QColor(theme.RED), 2))
        p.drawEllipse(QPointF(cx_car, cy), r, r)
        p.drawPixmap(int(cx_car - 14), int(cy - 14), icons.pixmap("car", theme.RED, 28))

        # 2. Pedestrian Node (Blue/Cyan circle)
        g2 = QRadialGradient(QPointF(cx_ped, cy), r)
        g2.setColorAt(0, theme.qcolor(theme.CYAN, 60))
        g2.setColorAt(1, theme.qcolor(theme.CYAN, 15))
        p.setBrush(QBrush(g2))
        p.setPen(QPen(QColor(theme.CYAN), 2))
        p.drawEllipse(QPointF(cx_ped, cy), r, r)
        p.drawPixmap(int(cx_ped - 14), int(cy - 14), icons.pixmap("person-standing", theme.CYAN, 28))

        # 3. Bicycle Node (Green circle)
        g3 = QRadialGradient(QPointF(cx_bike, cy), r)
        g3.setColorAt(0, theme.qcolor(theme.GREEN, 60))
        g3.setColorAt(1, theme.qcolor(theme.GREEN, 15))
        p.setBrush(QBrush(g3))
        p.setPen(QPen(QColor(theme.GREEN), 2))
        p.drawEllipse(QPointF(cx_bike, cy), r, r)
        p.drawPixmap(int(cx_bike - 14), int(cy - 14), icons.pixmap("bike", theme.GREEN, 28))


class HeatLegend(QFrame):
    """Small legend box with colored dots, like the design."""
    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background: {theme.rgba('#020815', 200)}; border: 1px solid {theme.BORDER}; border-radius: 8px;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 12, 8)
        lay.setSpacing(4)
        for name, color in (("Critical", theme.RED), ("High", "#FF8A1F"), ("Medium", theme.YELLOW),
                            ("Low", theme.GREEN), ("Info", theme.BLUE)):
            row = QHBoxLayout()
            row.setSpacing(8)
            dot = QLabel()
            dot.setFixedSize(10, 10)
            dot.setStyleSheet(f"background: {color}; border-radius: 5px; border: none;")
            txt = QLabel(name)
            txt.setStyleSheet(f"color: {theme.DIM}; font-size: 11px; border: none; background: transparent;")
            row.addWidget(dot)
            row.addWidget(txt)
            lay.addLayout(row)
