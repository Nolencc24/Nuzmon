"""The app's stylesheet. Colors live here so every page looks the same."""

import os

# Qt stylesheets need image paths with forward slashes, even on Windows.
ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets").replace("\\", "/")

STYLE = """
QWidget { background: #16181d; color: #d8dce4; font-family: 'Segoe UI', sans-serif; font-size: 12px; }
QLabel { background: transparent; }
QTabWidget::pane { border: none; }
QTabBar::tab { background: #22252c; color: #9aa3b5; padding: 7px 18px; min-width: 70px; min-height: 16px;
               border-radius: 4px; margin-right: 4px; }
QTabBar::tab:hover { background: #2c3039; }
QTabBar::tab:selected { background: #3a6ff7; color: white; }
QFrame#card { background: #1f2229; border: 1px solid #2c3039; border-radius: 8px; }
QFrame#row  { background: #1f2229; border: 1px solid #2c3039; border-radius: 6px; }
QFrame#row:hover { border-color: #3a6ff7; }
QFrame#infopanel { background: #1a1d23; border: 1px dashed #343946; border-radius: 8px; }
QLabel#section { font-size: 13px; font-weight: 600; color: #9aa3b5; letter-spacing: 1px; }
QLabel#rowname { font-weight: 600; }
QLabel#name { font-size: 15px; font-weight: 600; }
QLabel#dim  { color: #7d8492; }
QLabel#cell { font-family: Consolas, 'DejaVu Sans Mono', monospace; }
QProgressBar { background: #2c3039; border: none; border-radius: 4px; height: 8px; text-align: center; }
QFrame#calcside { background: #1f2229; border: 1px solid #2c3039; border-radius: 8px; }
QComboBox { background: #262a32; border: 1px solid #343946; border-radius: 4px; padding: 3px 6px; min-height: 18px; }
QComboBox:focus { border-color: #3a6ff7; }
QComboBox::drop-down { border: none; width: 18px; }
QComboBox::down-arrow { image: url("ASSETS/down_arrow.svg"); width: 10px; height: 6px; }
QComboBox QLineEdit { background: transparent; border: none; padding: 0; }
QAbstractItemView { background: #22252c; border: 1px solid #343946; selection-background-color: #3a6ff7;
                    selection-color: white; outline: none; }
QLineEdit#statedit { background: #262a32; border: 1px solid transparent; border-radius: 3px; padding: 0 3px;
                     font-family: Consolas, 'DejaVu Sans Mono', monospace; }
QLineEdit#statedit:hover { border-color: #3a3f4b; }
QLineEdit#statedit:focus { border-color: #3a6ff7; }
QLabel#movetag { color: #9aa3b5; font-size: 11px; }
QLabel#speed { color: #9aa3b5; }
QComboBox#stage { min-width: 34px; font-family: Consolas, 'DejaVu Sans Mono', monospace; }
QLineEdit#power { background: #262a32; border: 1px solid #343946; border-radius: 4px; padding: 3px 2px; min-height: 18px; }
QLineEdit#power:focus { border-color: #3a6ff7; }
QComboBox:disabled, QLineEdit:disabled, QPushButton:disabled { color: #4a505c; }
QPushButton#crit { background: #262a32; border: 1px solid #343946; border-radius: 4px; padding: 4px 0; color: #9aa3b5; }
QPushButton#crit:hover { border-color: #4a5160; }
QPushButton#reset { background: #3a6ff7; border: 1px solid #3a6ff7; border-radius: 4px; padding: 4px 8px; color: white; }
QPushButton#reset:hover { background: #4b7cf8; }
QPushButton#reset:disabled { background: #262a32; border-color: #343946; color: #4a505c; }
QPushButton#crit:checked { background: #e8a13a; border-color: #e8a13a; color: #16181d; font-weight: 600; }
""".replace("ASSETS", ASSETS)
