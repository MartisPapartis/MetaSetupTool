"""Entry point for the Meta Campaign Setup Tool."""

import sys
import os
import logging
from pathlib import Path

# Ensure the project root is on the path when run as a script
sys.path.insert(0, os.path.dirname(__file__))

# pylint: disable=wrong-import-position
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont
from app.ui.main_window import MainWindow
# pylint: enable=wrong-import-position

_LOG_DIR = Path.home() / ".metasetuptool" / "logs"


def _setup_logging() -> None:
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(_LOG_DIR / "app.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def main() -> None:
    _setup_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("Meta Campaign Setup Tool")
    app.setOrganizationName("MetaSetupTool")

    font = QFont("Segoe UI", 10)
    app.setFont(font)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
