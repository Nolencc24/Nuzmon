"""
SoulSilver tracker window.

Reads the dump file written by tracker.lua (running inside DeSmuME), decrypts it
with decoder.py, and shows your party and the opponent in a separate window.

    python tracker.py                    # watches ss_dump.txt next to this file
    python tracker.py --file C:/path/ss_dump.txt
    python tracker.py --demo             # sample data, no emulator needed
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QApplication, QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QMainWindow, QProgressBar, QTabWidget, QVBoxLayout, QWidget)

from decoder import NATURES, Pokemon, read_dump

HERE = os.path.dirname(os.path.abspath(__file__))
DISPLAY_ORDER = ["HP", "Atk", "Def", "SpA", "SpD", "Spe"]  # summary-screen order
NATURE_STATS = ["Atk", "Def", "Spe", "SpA", "SpD"]          # order used by nature math

STYLE = """
QWidget { background: #16181d; color: #d8dce4; font-family: 'Segoe UI', sans-serif; font-size: 12px; }
QLabel { background: transparent; }
QTabWidget::pane { border: none; }
QTabBar::tab { background: #22252c; padding: 6px 18px; border-radius: 4px; margin-right: 4px; }
QTabBar::tab:selected { background: #3a6ff7; color: white; }
QFrame#card { background: #1f2229; border: 1px solid #2c3039; border-radius: 8px; }
QLabel#name { font-size: 15px; font-weight: 600; }
QLabel#dim  { color: #7d8492; }
QLabel#cell { font-family: Consolas, 'DejaVu Sans Mono', monospace; }
QProgressBar { background: #2c3039; border: none; border-radius: 4px; height: 8px; text-align: center; }
"""


def nature_effect(nature: str) -> tuple[str | None, str | None]:
    """Returns (boosted stat, lowered stat), or (None, None) for neutral natures."""
    n = NATURES.index(nature)
    up, down = n // 5, n % 5
    return (None, None) if up == down else (NATURE_STATS[up], NATURE_STATS[down])


class Card(QFrame):
    """One Pokémon. Widgets are built once and updated in place, so nothing flickers."""

    def __init__(self):
        super().__init__()
        self.setObjectName("card")
        self.setMinimumWidth(270)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)

        top = QHBoxLayout()
        self.name = QLabel(objectName="name")
        self.level = QLabel(objectName="dim")
        top.addWidget(self.name)
        top.addStretch()
        top.addWidget(self.level)
        lay.addLayout(top)

        self.hpbar = QProgressBar(textVisible=False)
        self.hptext = QLabel(objectName="dim")
        lay.addWidget(self.hpbar)
        lay.addWidget(self.hptext)

        self.info = QLabel(objectName="dim")
        self.info.setWordWrap(True)
        lay.addWidget(self.info)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(2)
        self.cells = {"header": []}
        for c, h in enumerate(["", "Stat", "IV", "EV"]):
            lbl = QLabel(h, objectName="dim")
            lbl.setAlignment(Qt.AlignRight if c else Qt.AlignLeft)
            grid.addWidget(lbl, 0, c)
            self.cells["header"].append(lbl)
        for r, stat in enumerate(DISPLAY_ORDER, start=1):
            row = [QLabel(stat, objectName="cell")] + [QLabel(objectName="cell") for _ in range(3)]
            for c, lbl in enumerate(row):
                if c:
                    lbl.setAlignment(Qt.AlignRight)
                grid.addWidget(lbl, r, c)
            self.cells[stat] = row
        lay.addLayout(grid)

        self.extra = QLabel(objectName="dim")
        lay.addWidget(self.extra)
        self.moves = QLabel(objectName="cell")
        lay.addWidget(self.moves)
        lay.addStretch()
        self.show_mon(None)

    def show_mon(self, m: Pokemon | None):
        has = m is not None
        for w in (self.hpbar, self.hptext, self.info, self.extra, self.moves):
            w.setVisible(has)
        for row in self.cells.values():
            for lbl in row:
                lbl.setVisible(has)
        if not has:
            self.name.setText("—")
            self.level.setText("empty")
            return

        if m.is_egg:
            self.name.setText("Egg")
        else:
            self.name.setText(f"{m.species}{'  ★' if m.shiny else ''}  {m.gender}")
        self.level.setText(f"Lv {m.level}" if m.level is not None else "")

        hp, mx = m.hp or 0, m.max_hp or 1
        pct = hp / mx
        color = "#3ccf6e" if pct > 0.5 else "#f2c94c" if pct > 0.2 else "#eb5757"
        self.hpbar.setRange(0, mx)
        self.hpbar.setValue(hp)
        self.hpbar.setStyleSheet(f"QProgressBar::chunk {{ background: {color}; border-radius: 4px; }}")
        self.hptext.setText(f"HP {hp} / {mx}" + ("" if m.status == "OK" else f"   ·   {m.status}"))
        self.info.setText(f"{m.nature} · {m.ability}")

        up, down = nature_effect(m.nature)
        for stat in DISPLAY_ORDER:
            name, val, iv, ev = self.cells[stat]
            name.setStyleSheet("color:#ff7a7a" if stat == up else "color:#7ab0ff" if stat == down else "")
            val.setText(str(m.stats.get(stat, "?")))
            iv.setText(str(m.ivs[stat]))
            iv.setStyleSheet("color:#3ccf6e" if m.ivs[stat] == 31 else "color:#eb5757" if m.ivs[stat] == 0 else "")
            ev.setText(str(m.evs[stat]))

        hp_type, hp_pow = m.hidden_power
        self.extra.setText(f"EVs {sum(m.evs.values())}/510  ·  Hidden Power {hp_type} {hp_pow}")
        self.moves.setText("\n".join(f"{mv:<16}{pp:>3} PP" for mv, pp in m.moves) or "(no moves)")


class Team(QWidget):
    def __init__(self):
        super().__init__()
        grid = QGridLayout(self)
        grid.setSpacing(10)
        self.cards = [Card() for _ in range(6)]
        for i, c in enumerate(self.cards):
            grid.addWidget(c, i // 3, i % 3)

    def show_team(self, mons):
        for card, m in zip(self.cards, mons):
            card.show_mon(m)


class Tracker(QMainWindow):
    def __init__(self, path: str):
        super().__init__()
        self.path = path
        self.last_mtime = None
        self.setWindowTitle("SoulSilver Tracker")

        root = QWidget()
        lay = QVBoxLayout(root)
        self.tabs = QTabWidget()
        self.party, self.enemy = Team(), Team()
        self.tabs.addTab(self.party, "Your party")
        self.tabs.addTab(self.enemy, "Opponent")
        lay.addWidget(self.tabs)
        self.status = QLabel(objectName="dim")
        lay.addWidget(self.status)
        self.setCentralWidget(root)

        self.timer = QTimer(self, interval=250, timeout=self.poll)
        self.timer.start()
        self.poll()

    def poll(self):
        try:
            mtime = os.path.getmtime(self.path)
        except OSError:
            self.status.setText(f"Waiting for {self.path} … is tracker.lua running in DeSmuME?")
            return
        if mtime == self.last_mtime:
            return
        try:
            data = read_dump(self.path)
        except OSError:
            return  # file was being swapped; try again next tick
        self.last_mtime = mtime

        self.party.show_team(data["party"])
        self.enemy.show_team(data["enemy"])

        n_party = sum(m is not None for m in data["party"])
        n_enemy = sum(m is not None for m in data["enemy"])
        meta = data["meta"]
        msg = (f"Game {meta.get('game', '?')}  ·  base {meta.get('base', '?')}  ·  "
               f"frame {meta.get('frame', '?')}  ·  {n_party} party / {n_enemy} opponent slots decoded")
        if n_party == 0:
            msg += ("   ⚠ nothing passed the checksum: you may be on the title screen, "
                    "or the address in tracker.lua is wrong for your ROM")
        self.status.setText(msg)


def write_demo_file() -> str:
    """Fake dump built from the real sample Pokémon in test_decoder.py."""
    from decoder import encrypt
    from test_decoder import GEODUDE, SHINY_CUBONE, as_party

    p1 = encrypt(as_party(GEODUDE, 14, 22, 37)).hex()
    p2 = encrypt(as_party(SHINY_CUBONE, 9, 6, 28)).hex()
    empty = "00" * 236
    lines = ["frame=0", "game=DEMO", "base=0x00000000", f"P1={p1}", f"P2={p2}"]
    lines += [f"P{i}={empty}" for i in range(3, 7)]
    lines += [f"E1={p2}"] + [f"E{i}={empty}" for i in range(2, 7)]
    path = os.path.join(tempfile.gettempdir(), "ss_dump_demo.txt")
    with open(path, "w", encoding="ascii") as f:
        f.write("\n".join(lines) + "\n")
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", default=os.path.join(HERE, "ss_dump.txt"), help="dump file written by tracker.lua")
    ap.add_argument("--demo", action="store_true", help="show sample data instead of reading the emulator")
    args = ap.parse_args()

    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)
    win = Tracker(write_demo_file() if args.demo else args.file)
    win.resize(900, 640)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
