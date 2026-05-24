"""
MP3 Player — Application Entry Point

Creates the QApplication, applies the dark stylesheet, and opens the main
window.  Heavy initialisation is deferred to individual components so the
window appears quickly.

Run with:
    python main.py
"""

import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from ui.main_window import MainWindow

# User data directory (database, future preferences)
APP_DATA_DIR: Path = Path.home() / ".mp3player"
APP_DATA_DIR.mkdir(parents=True, exist_ok=True)


def _apply_stylesheet(app: QApplication) -> None:
    """Load assets/styles/dark_theme.qss and set it as the application style."""
    qss_path = Path(__file__).parent / "assets" / "styles" / "dark_theme.qss"
    if qss_path.exists():
        app.setStyleSheet(qss_path.read_text(encoding="utf-8"))
    else:
        print(f"[Warning] Stylesheet not found at {qss_path}")


def main() -> None:
    """Bootstrap the Qt application and enter the event loop."""
    app = QApplication(sys.argv)
    app.setApplicationName("MP3 Player")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("AudioLab")

    _apply_stylesheet(app)

    window = MainWindow(data_dir=APP_DATA_DIR)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
