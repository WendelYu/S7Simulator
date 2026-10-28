from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication

from . import motion
from . import __version__
from .models import Project
from .window import SETTINGS_APP, SETTINGS_ORG, MainWindow


def _system_dark(app):
    try:
        return app.styleHints().colorScheme() == Qt.ColorScheme.Dark
    except AttributeError:
        return False


def main():
    parser = argparse.ArgumentParser(description="S7 Studio — graphical S7 PLC data simulator")
    parser.add_argument("project", nargs="?", help="Path to a .s7sim.json project")
    parser.add_argument("--screenshot", help="Render a screenshot to this PNG path and exit")
    parser.add_argument(
        "--theme", choices=("auto", "light", "dark"),
        help="Theme override (default: last used, otherwise light)",
    )
    parser.add_argument("--no-motion", action="store_true", help="Disable interface animations")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    app = QApplication(sys.argv[:1])
    app.setApplicationName(SETTINGS_APP)
    app.setApplicationVersion(__version__)
    app.setOrganizationName(SETTINGS_ORG)
    app.setStyle("Fusion")
    font = QFont("PingFang SC" if sys.platform == "darwin" else "Microsoft YaHei", 10)
    app.setFont(font)
    icon = QIcon(str(Path(__file__).parent / "assets" / "icon.svg"))
    app.setWindowIcon(icon)

    settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
    mode = args.theme or settings.value("ui/theme", "light")
    if mode not in {"auto", "light", "dark"}:
        mode = "light"
    dark = _system_dark(app) if mode == "auto" else mode == "dark"
    if args.no_motion:
        motion.set_enabled(False)
    else:
        motion.set_enabled(settings.value("ui/motion", True, type=bool))

    try:
        project = Project.load(args.project) if args.project else None
    except Exception as exc:
        parser.exit(1, f"无法打开项目：{exc}\n")

    window = MainWindow(project, dark=dark, theme_mode=mode)
    if args.project:
        window.path = Path(args.project)
        window.update_title()
    window.show()
    if args.screenshot:
        target = Path(args.screenshot).expanduser()

        def capture():
            pixmap = window.grab()
            target.parent.mkdir(parents=True, exist_ok=True)
            pixmap.save(str(target))
            window.close()

        QTimer.singleShot(1600, capture)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
