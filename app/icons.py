"""Icons: thin outline icons (Lucide, ISC license) drawn in any color. The drawings are in icon_data.py."""
from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QPixmap, QPainter, QIcon
from PySide6.QtSvg import QSvgRenderer
from icon_data import ICONS

_cache = {}


def pixmap(name, color="#FFFFFF", size=20, stroke=2.0):
    """A crisp icon picture of the given color and size (drawn at 2x for sharp screens)."""
    key = (name, color, size, stroke)
    if key in _cache:
        return _cache[key]
    scale = 2
    pm = QPixmap(size * scale, size * scale)
    pm.fill(Qt.transparent)
    svg = ICONS.get(name)
    if svg:
        svg = svg.replace("currentColor", color).replace('stroke-width="2"', f'stroke-width="{stroke}"')
        renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
        painter = QPainter(pm)
        renderer.render(painter)
        painter.end()                          # (an unknown icon name stays empty instead of crashing)
    pm.setDevicePixelRatio(scale)
    _cache[key] = pm
    return pm


def icon(name, color="#FFFFFF", size=20):
    return QIcon(pixmap(name, color, size))


def icon_states(name, off_color, on_color, size=20):
    """An icon that changes color when its (checkable) button is checked."""
    ic = QIcon()
    ic.addPixmap(pixmap(name, off_color, size), QIcon.Normal, QIcon.Off)
    ic.addPixmap(pixmap(name, on_color, size), QIcon.Normal, QIcon.On)
    ic.addPixmap(pixmap(name, on_color, size), QIcon.Active, QIcon.Off)
    return ic
