"""
SoulSilver tracker window.

Reads your party and the opponent straight out of DeSmuME's memory (no Lua script
needed), decrypts them with decoder.py, and shows them in a separate window.

    python tracker.py                    # read DeSmuME directly (recommended)
    python tracker.py --lua              # read ss_dump.txt written by tracker.lua instead
    python tracker.py --lua --file C:/path/ss_dump.txt
    python tracker.py --demo             # sample data, no emulator needed
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QApplication, QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QMainWindow, QProgressBar, QVBoxLayout, QWidget)

from decoder import NATURES, IncompleteDump, Pokemon, read_dump

HERE = os.path.dirname(os.path.abspath(__file__))
DISPLAY_ORDER = ["HP", "Atk", "Def", "SpA", "SpD", "Spe"]  # summary-screen order
NATURE_STATS = ["Atk", "Def", "Spe", "SpA", "SpD"]          # order used by nature math

STYLE = """
QWidget { background: #16181d; color: #d8dce4; font-family: 'Segoe UI', sans-serif; font-size: 12px; }
QLabel { background: transparent; }
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


def nature_effect(nature: str) -> tuple[str | None, str | None]:
    """Returns (boosted stat, lowered stat), or (None, None) for neutral natures."""
    n = NATURES.index(nature)
    up, down = n // 5, n % 5
    return (None, None) if up == down else (NATURE_STATS[up], NATURE_STATS[down])


class Card(QFrame):
    """One Pokémon, fully expanded. Widgets are built once and updated in place, so nothing flickers.

    wide=True lays the card out in three columns (summary | stats | moves) instead of
    one tall column, which is how the lead Pokémon is shown.
    """

    def __init__(self, wide: bool = False):
        super().__init__()
        self.setObjectName("card")
        self.setMinimumWidth(270)
        outer = QHBoxLayout(self) if wide else QVBoxLayout(self)
        outer.setContentsMargins(12, 10, 12, 10)
        outer.setSpacing(18 if wide else 6)
        lay = QVBoxLayout()          # column 1: name, HP, nature/ability
        lay.setSpacing(6)
        outer.addLayout(lay, 3 if wide else 0)

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

        self.extra = QLabel(objectName="dim")
        self.extra.setWordWrap(True)
        self.moves = QLabel(objectName="cell")

        if wide:
            lay.addWidget(self.extra)
            lay.addStretch()
            col2, col3 = QVBoxLayout(), QVBoxLayout()   # column 2: stat grid, column 3: moves
            col2.addLayout(grid)
            col2.addStretch()
            col3.addWidget(QLabel("Moves", objectName="dim"))
            col3.addWidget(self.moves)
            col3.addStretch()
            outer.addLayout(col2, 3)
            outer.addLayout(col3, 2)
        else:
            lay.addLayout(grid)
            lay.addWidget(self.extra)
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


class Row(QFrame):
    """A thin one-line summary for party slots 2-6: name, level, HP bar, status."""

    def __init__(self):
        super().__init__()
        self.setObjectName("row")
        self.setFixedHeight(34)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 4, 10, 4)
        lay.setSpacing(10)
        self.name = QLabel(objectName="rowname")
        self.name.setMinimumWidth(110)
        self.level = QLabel(objectName="dim")
        self.level.setMinimumWidth(40)
        self.hpbar = QProgressBar(textVisible=False)
        self.hpbar.setFixedHeight(8)
        self.hptext = QLabel(objectName="cell")
        self.hptext.setMinimumWidth(70)
        self.hptext.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.status = QLabel(objectName="dim")
        self.status.setMinimumWidth(70)
        lay.addWidget(self.name)
        lay.addWidget(self.level)
        lay.addWidget(self.hpbar, 1)
        lay.addWidget(self.hptext)
        lay.addWidget(self.status)
        self.show_mon(None)

    def show_mon(self, m: Pokemon | None):
        has = m is not None
        for w in (self.hpbar, self.hptext, self.status):
            w.setVisible(has)

        if not has:
            self.name.setText("—")
            self.level.setText("")
            return
        
        self.name.setText("Egg" if m.is_egg else f"{m.species}{' ★' if m.shiny else ''}")
        self.level.setText(f"Lv {m.level}" if m.level is not None else "")
        hp, mx = m.hp or 0, m.max_hp or 1
        pct = hp / mx
        color = "#3ccf6e" if pct > 0.5 else "#f2c94c" if pct > 0.2 else "#eb5757"
        self.hpbar.setRange(0, mx)
        self.hpbar.setValue(hp)
        self.hpbar.setStyleSheet(f"QProgressBar::chunk {{ background: {color}; border-radius: 4px; }}")
        self.hptext.setText(f"{hp}/{mx}")
        self.status.setText("" if m.status == "OK" else m.status)


class TeamSection(QWidget):
    """The featured Pokémon as a big expanded card on the left, the rest as thin rows.

    Outside battle the featured one is party slot 1; in battle it's whoever is out.
    """

    def __init__(self, title: str):
        super().__init__()
        self.title = title.upper()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)
        self.heading = QLabel(self.title, objectName="section")
        outer.addWidget(self.heading)

        body = QHBoxLayout()
        body.setSpacing(10)
        self.lead = Card(wide=True)
        rows = QVBoxLayout()
        rows.setSpacing(4)
        self.rows = [Row() for _ in range(5)]
        for r in self.rows:
            rows.addWidget(r)
        rows.addStretch()
        body.addWidget(self.lead, 3)   # lead card gets 3/5 of the width...
        body.addLayout(rows, 2)        # ...the rows get 2/5
        outer.addLayout(body)

    def show_team(self, mons, active: int | None = None):
        """active: index of the Pokémon currently in battle (None outside battle)."""
        featured = active if active is not None and mons[active] is not None else 0
        self.lead.show_mon(mons[featured])
        others = [m for i, m in enumerate(mons) if i != featured]   # keep party order
       
        for row, m in zip(self.rows, others):
            row.show_mon(m)
        self.heading.setText(f"{self.title}  ·  IN BATTLE" if active is not None else self.title)


class InfoPanel(QFrame):
    """The open space between the two teams. Add your own widgets to self.body."""

    def __init__(self):
        super().__init__()
        self.setObjectName("infopanel")
        self.setMinimumHeight(110)
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(14, 10, 14, 10)
        self.body.addWidget(QLabel("CALCULATOR", objectName="section"))
        self.body.addStretch()
        self.moves = QLabel(objectName="cell")

        


class FileSource:
    """Data source: the ss_dump.txt file written by tracker.lua."""

    def __init__(self, path: str):
        self.path = path
        self.last_mtime = None

    def poll(self):
        """Returns (data or None, status message or None). data is None when nothing changed."""
        try:
            mtime = os.path.getmtime(self.path)
        except OSError:
            return None, f"Waiting for {self.path} … is tracker.lua running in DeSmuME?"
        
        if mtime == self.last_mtime:
            return None, None
       
        try:
            data = read_dump(self.path)
        except (OSError, IncompleteDump):
            return None, None  # caught tracker.lua mid-write; try again next tick
        self.last_mtime = mtime
        data["meta"]["source"] = os.path.basename(self.path)
        return data, None


class Tracker(QMainWindow):
    def __init__(self, source):
        super().__init__()
        self.source = source
        self.setWindowTitle("SoulSilver Tracker")

        root = QWidget()
        lay = QVBoxLayout(root)
        lay.setContentsMargins(12, 10, 12, 8)
        lay.setSpacing(10)
        self.party = TeamSection("Your party")
        self.info = InfoPanel()
        self.enemy = TeamSection("Opponent")
        lay.addWidget(self.party)
        lay.addWidget(self.info, 1)    # the middle panel takes up any spare height
        lay.addWidget(self.enemy)
        self.status = QLabel(objectName="dim")
        lay.addWidget(self.status)
        self.setCentralWidget(root)

        self.timer = QTimer(self, interval=250, timeout=self.poll)
        self.timer.start()
        self.poll()

    def poll(self):
        data, message = self.source.poll()
        if message:
            self.status.setText(message)
       
        if data is None:
            return

        self.party.show_team(data["party"], data.get("party_active"))
        self.enemy.show_team(data["enemy"], data.get("enemy_active"))

        n_party = sum(m is not None for m in data["party"])
        n_enemy = sum(m is not None for m in data["enemy"])
        meta = data["meta"]
        msg = (f"{meta.get('source', '')}  ·  game {meta.get('game', '?')}  ·  base {meta.get('base', '?')}  ·  "
               f"{n_party} party / {n_enemy} opponent slots decoded")
      
        if n_party == 0:
            msg += (" nothing passed the checksum: you may be on the title screen, "
                    "or the address is wrong for your ROM")
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
    lines += [f"E1={p2}", f"E2={p1}"] + [f"E{i}={empty}" for i in range(3, 7)]
    path = os.path.join(tempfile.gettempdir(), "ss_dump_demo.txt")
   
    with open(path, "w", encoding="ascii") as f:
        f.write("\n".join(lines) + "\n")
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lua", action="store_true", help="read the file written by tracker.lua instead of DeSmuME's memory")
    ap.add_argument("--file", default=os.path.join(HERE, "ss_dump.txt"), help="dump file for --lua mode")
    ap.add_argument("--pid", type=int, help="DeSmuME process ID, if auto-detection picks the wrong one")
    ap.add_argument("--demo", action="store_true", help="show sample data instead of reading the emulator")
    args = ap.parse_args()

    if args.demo:
        source = FileSource(write_demo_file())
    elif args.lua:
        source = FileSource(args.file)
    else:
        from memreader import MemorySource
        source = MemorySource(pid=args.pid)

    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)
    win = Tracker(source)
    win.resize(1000, 760)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()