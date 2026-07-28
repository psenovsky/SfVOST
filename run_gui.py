#!/usr/bin/env python3
"""
Spouštěč GUI aplikace SFVOST.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from gui.main_window import MainWindow
from PyQt6.QtWidgets import QApplication

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
