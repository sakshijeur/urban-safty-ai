"""Start the app:   python main.py        (real use)
                  python main.py --demo   (fake live events, for showing the screens)
Run it from inside the app folder."""
import os
import sys

if sys.platform == "win32":
    os.environ.setdefault("QT_QPA_PLATFORM", "windows:fontengine=freetype")    # smoother, more even text than the default

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(HERE, "..", "tracking"))      # lets the app use the tracking code (app files come first)

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication
import theme
from fake_data import EventStore
from database import Database
from main_window import MainWindow


def main():
    demo = "--demo" in sys.argv
    app = QApplication([a for a in sys.argv if a != "--demo"])
    theme.load_fonts()
    body = QFont(theme.pick_font(theme.BODY_FONTS), 11)
    body.setHintingPreference(QFont.PreferVerticalHinting)      # crisp lines, smooth curves
    body.setStyleStrategy(QFont.PreferAntialias)
    app.setFont(body)
    app.setStyleSheet(theme.STYLESHEET)
    db = None if demo else Database(os.path.join(HERE, "..", "data", "safety.db"))     # saved runs live in Urban_Safety_AI/data
    store = EventStore(demo=demo, db=db)
    window = MainWindow(store)
    window.showMaximized()          # fill the usable screen; the layout adapts to small screens
    if demo:
        store.start_demo(2500)    # a new fake event every 2.5 seconds
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
