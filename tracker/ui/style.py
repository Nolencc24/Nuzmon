"""The app's stylesheet. Colors live here so every page looks the same."""

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
QFrame#infopanel { background: #1a1d23; border: 1px dashed #343946; border-radius: 8px; }
QLabel#section { font-size: 13px; font-weight: 600; color: #9aa3b5; letter-spacing: 1px; }
QLabel#rowname { font-weight: 600; }
QLabel#name { font-size: 15px; font-weight: 600; }
QLabel#dim  { color: #7d8492; }
QLabel#cell { font-family: Consolas, 'DejaVu Sans Mono', monospace; }
QProgressBar { background: #2c3039; border: none; border-radius: 4px; height: 8px; text-align: center; }
"""
