"""The main window: a row of tabs, one page per tab, and a status bar.

The window polls the data source once and hands the result to every page that has an
update_data(data) method, so pages never read the emulator themselves.

To add a page: make a QWidget in tracker/ui/pages/, give it update_data(data) if it
needs game data, and add it to PAGES below.
"""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QLabel, QMainWindow, QTabWidget, QVBoxLayout, QWidget

from tracker.ui.pages.battle_page import BattlePage
from tracker.ui.pages.blank_page import BlankPage

# (tab label, page class). Blank labels are fine for now.
PAGES = [
    ("Battle", BattlePage),
    ("", BlankPage),
    ("", BlankPage),
    ("", BlankPage),
    ("", BlankPage),
    ("", BlankPage),
]

POLL_MS = 250


class MainWindow(QMainWindow):
    def __init__(self, source):
        super().__init__()
        self.source = source
        self.setWindowTitle("Nuzmon")

        root = QWidget()
        lay = QVBoxLayout(root)
        lay.setContentsMargins(12, 10, 12, 8)
        lay.setSpacing(8)

        self.tabs = QTabWidget()
        self.pages = []

        for label, page_class in PAGES:
            page = page_class()
            self.tabs.addTab(page, label)
            self.pages.append(page)
        lay.addWidget(self.tabs, 1)

        self.status = QLabel(objectName="dim")
        lay.addWidget(self.status)
        self.setCentralWidget(root)

        self.timer = QTimer(self, interval=POLL_MS, timeout=self.poll)
        self.timer.start()
        self.poll()

    def poll(self):
        data, message = self.source.poll()
        if message:
            self.status.setText(message)
        if data is None:
            return

        for page in self.pages:
            if hasattr(page, "update_data"):
                page.update_data(data)

        n_party = sum(m is not None for m in data["party"])
        n_enemy = sum(m is not None for m in data["enemy"])
        meta = data["meta"]
        msg = (f"{meta.get('source', '')}  ·  game {meta.get('game', '?')}  ·  base {meta.get('base', '?')}  ·  "
               f"{n_party} party / {n_enemy} opponent slots decoded")
        
        if n_party == 0:
            msg += ("   ⚠ nothing passed the checksum: you may be on the title screen, "
                    "or the address is wrong for your ROM")
        self.status.setText(msg)
