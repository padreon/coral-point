import sys
import os

# xcb is required on headless Linux (Codespaces/CI); Windows and macOS
# auto-detect the correct platform plugin so we must not override them.
if sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont
from src.ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("coralX")
    app.setOrganizationName("coralX")
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
