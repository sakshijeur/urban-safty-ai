"""Look of the app, matched to the design PDF (colors were measured from the design pixels).
Change the look here only."""
import base64
from PySide6.QtCore import QByteArray
from PySide6.QtGui import QColor, QFont, QFontDatabase

APP_NAME = "URBAN SAFETY AI"            # one name everywhere (the design images used two different names)
APP_SUBTITLE = "AI-Based Urban Road Safety & Traffic Intelligence System"

# ---- surfaces (from the design)
BG, HEADER_BG, SIDEBAR_BG = "#020815", "#010513", "#061221"
PANEL, PANEL_TOP = "#071424", "#0A1A2E"
ROW, ROW_BORDER = "#0E1A2A", "#172A3F"
BORDER, BORDER_HI = "#18283B", "#2A4A6E"
TEXT, DIM = "#FFFFFF", "#8DA2BC"
ACCENT, CYAN = "#007AFF", "#1D9BD3"          # subtitle blue, active-menu bar

# ---- meaning colors (handbook 11.2): the same everywhere, including the video overlay
GREEN, YELLOW, RED, BLUE, PURPLE = "#2ECC71", "#F1C40F", "#FF4D4F", "#3FA7FF", "#A66BFF"
SEVERITY_COLOR = {"CRITICAL": RED, "HIGH": RED, "MEDIUM": YELLOW, "LOW": GREEN, "INFO": BLUE}
# alert tiles (square icon boxes in the alert feed)
TILE = {"red": "#B8322F", "amber": "#C98A12", "green": "#3C9A5A", "purple": "#7E4BD6", "blue": "#1F6FD0"}
# counter-card icon colors (from the design)
KPI = {"vehicles": "#09B0F1", "pedestrians": "#2AE1A0", "near_misses": "#F9A900", "sudden_braking": "#F62C12",
       "wrong_side": "#F32718", "restricted_entry": "#FCBF04", "emergency_vehicles": "#6FD23C", "high_risk": "#E42B29",
       "duration": "#3FA7FF", "traffic_level": "#F62C12"}

# system fonts only (no font files needed)
# Fonts. FONT_PRESET picks the look; change this one word to try another:
#   "soft"    Barlow Condensed titles + Barlow text, light weights (packed in font_data.py, same on every computer)
#   "windows" the Windows 11 system fonts (Segoe UI), the plainest and smoothest
#   "dash"    Bahnschrift (the DIN-style dashboard font that comes with Windows 10/11) for titles, Segoe UI for text
FONT_PRESET = "soft"
_PRESETS = {"soft": ("SafetyHead", "SafetyTextMed", "SafetyTextSemi"),
            "windows": ("Segoe UI Semibold", "Segoe UI", "Segoe UI Semibold"),
            "dash": ("Bahnschrift SemiBold SemiConden", "Segoe UI", "Segoe UI Semibold")}
HEADING_FONT, BODY_FONT, STRONG_FONT = _PRESETS[FONT_PRESET]
STRONG_CSS = f"font-family: '{STRONG_FONT}';"          # use this instead of font-weight: bold (no faked bold)
HEADING_FONTS = [HEADING_FONT, "Segoe UI", "Arial"]
BODY_FONTS = [BODY_FONT, "Segoe UI", "Arial"]


def load_fonts():
    """Register the packed fonts with Qt. Call once, right after creating the QApplication."""
    from font_data import FONTS
    for data in FONTS.values():
        QFontDatabase.addApplicationFontFromData(QByteArray(base64.b64decode(data)))


def rgba(hex_color, alpha):
    """'#RRGGBB' + alpha 0-255 -> 'rgba(r, g, b, a)' (Qt stylesheets do not accept #RRGGBBAA)."""
    h = hex_color.lstrip("#")
    return f"rgba({int(h[0:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)}, {alpha})"


def qcolor(hex_color, alpha=255):
    """A drawing color (QColor) with transparency. Use this in painting code; rgba() is for stylesheets only."""
    c = QColor(hex_color)
    c.setAlpha(alpha)
    return c


def pick_font(candidates):
    """First font from the list that is installed on this computer."""
    installed = set(QFontDatabase.families())
    for name in candidates:
        if name in installed:
            return name
    return candidates[-1]


def heading_font(size, bold=True):
    """Font for titles and big numbers. The weight comes from the font itself (SemiBold), never faked."""
    f = QFont(pick_font(HEADING_FONTS), size)
    f.setHintingPreference(QFont.PreferNoHinting)          # smooth outlines at large sizes
    f.setStyleStrategy(QFont.PreferAntialias)
    return f


def pill_style(color, filled=False):
    """Style for a small rounded status label (severity / status)."""
    bg = rgba(color, 70 if filled else 36)
    return (f"color: {color}; background: {bg}; border: 1px solid {rgba(color, 140)}; border-radius: 10px; "
            f"padding: 2px 10px; {STRONG_CSS} font-size: 11px;")


STYLESHEET = f"""
QWidget {{ color: {TEXT}; }}
#root {{ background: {BG}; }}
#header {{ background: {HEADER_BG}; border-bottom: 1px solid {BORDER}; }}
#sidebar {{ background: {SIDEBAR_BG}; border-right: 1px solid {BORDER}; }}

#panel {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {PANEL_TOP}, stop:1 {PANEL});
          border: 1px solid {BORDER}; border-radius: 10px; }}
#card {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {PANEL_TOP}, stop:1 {PANEL});
         border: 1px solid {BORDER}; border-radius: 10px; }}
#card:hover {{ border: 1px solid {BORDER_HI}; }}
#headerBox {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 10px; }}
#statusBox {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 10px; }}

#panelTitle {{ color: {TEXT}; {STRONG_CSS} font-size: 12px; letter-spacing: 0.8px; background: transparent; }}
#cardLabel {{ color: {DIM}; font-size: 10px; {STRONG_CSS} letter-spacing: 0.3px; background: transparent; }}
#dim {{ color: {DIM}; background: transparent; }}
#subtitle {{ color: {ACCENT}; {STRONG_CSS} background: transparent; }}
QLabel {{ background: transparent; }}

#navButton {{ text-align: left; padding: 12px 16px; border: none; border-left: 3px solid transparent;
              color: {DIM}; font-size: 13px; {STRONG_CSS} background: transparent; }}
#navButton:hover {{ color: {TEXT}; background: {rgba("#1E3F62", 90)}; }}
#navButton:checked {{ color: {TEXT}; border-left: 3px solid {CYAN};
                      background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1E3F62, stop:1 {SIDEBAR_BG}); }}

QLineEdit, QComboBox {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 8px; padding: 8px 10px; }}
QLineEdit:focus, QComboBox:focus {{ border: 1px solid {CYAN}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{ background: {PANEL}; selection-background-color: #13304F; border: 1px solid {BORDER}; }}
QCheckBox {{ spacing: 8px; color: {DIM}; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 4px; border: 1px solid {BORDER_HI}; background: {PANEL}; }}
QCheckBox::indicator:checked {{ background: {CYAN}; border: 1px solid {CYAN}; }}

QTableWidget {{ background: transparent; border: none; gridline-color: transparent; selection-background-color: transparent; outline: none; }}
QTableWidget::item {{ padding: 6px; border-bottom: 1px solid #10203A; }}
QTableWidget::item:selected {{ background: {rgba("#1E5FA8", 60)}; }}
QHeaderView {{ background: transparent; }}
QHeaderView::section {{ background: transparent; color: {CYAN}; border: none; border-bottom: 1px solid {BORDER};
                        padding: 8px; {STRONG_CSS} }}
QTableCornerButton::section {{ background: transparent; border: none; }}

QPushButton {{ {STRONG_CSS} }}
QPushButton#primary {{ background: {ACCENT}; color: white; border: none; border-radius: 8px; padding: 9px 16px; }}
QPushButton#primary:hover {{ background: #2B8CFF; }}
QPushButton#success {{ background: #27AE60; color: white; border: none; border-radius: 8px; padding: 9px 16px; }}
QPushButton#success:hover {{ background: #2ECC71; }}
QPushButton#danger {{ background: #C0392B; color: white; border: none; border-radius: 8px; padding: 9px 16px; }}
QPushButton#danger:hover {{ background: #D84A3B; }}
QPushButton#ghost {{ background: transparent; color: {TEXT}; border: 1px solid {BORDER_HI}; border-radius: 8px; padding: 9px 16px; }}
QPushButton#ghost:hover {{ background: {rgba("#1E5FA8", 50)}; border: 1px solid {CYAN}; }}
QPushButton#tabBtn {{ background: transparent; color: {DIM}; border: 1px solid {BORDER}; border-radius: 6px; padding: 6px 12px; }}
QPushButton#tabBtn:checked {{ background: {rgba(CYAN, 40)}; color: white; border: 1px solid {CYAN}; }}
QPushButton:disabled {{ color: #4A5A70; border-color: #16273A; background: transparent; }}
QPushButton#primary:disabled, QPushButton#danger:disabled, QPushButton#success:disabled {{ background: #0F2036; color: #4A5A70; }}
#bell {{ background: transparent; border: none; }}

QSlider::groove:horizontal {{ height: 6px; background: #0E1E32; border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: {CYAN}; border-radius: 3px; }}
QSlider::handle:horizontal {{ background: white; border: 2px solid {CYAN}; width: 16px; margin: -5px 0; border-radius: 8px; }}
QSlider::handle:horizontal:hover {{ background: {CYAN}; border: 2px solid white; }}

QDateEdit {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 8px; padding: 8px 10px; color: {TEXT}; }}
QDateEdit::drop-down {{ border: none; width: 24px; }}

QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #1B3350; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: #2A4A6E; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QToolTip {{ background: {PANEL}; color: {TEXT}; border: 1px solid {BORDER_HI}; padding: 4px 8px; }}
"""
