"""The damage calculator in the middle of the Battle tab.

    InfoPanel           the whole calculator: a "You" side and a "Foe" side
      CalcSide          one side: which Pokémon + 4 move rows
        MoveRow         move | base power | type | physical/special | crit

The foe's side is mirrored, so each side's move boxes sit along the panel's outer edge.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QVBoxLayout)

from tracker.game import gamedata
from tracker.ui.widgets import MovePicker

CATEGORIES = ["Physical", "Special", "Status"]


class MoveRow:
    """One move slot and its adjustable settings. Not a widget itself: the widgets are
    placed into the side's grid so every row's columns line up."""

    def __init__(self):
        self.picker = MovePicker()

        self.power = QLineEdit(objectName="power")   # editable base power (numbers 0-999 only)
        self.power.setValidator(QIntValidator(0, 999, self.power))
        self.power.setAlignment(Qt.AlignCenter)
        self.power.setFixedWidth(46)
        self.power.setToolTip("Base power")

        self.type = QComboBox()
        self.type.addItems(gamedata.types() + ["???"])
        self.type.setFixedWidth(92)
        self.type.setToolTip("Move type")

        self.category = QComboBox()
        self.category.addItems(CATEGORIES)
        self.category.setFixedWidth(84)
        self.category.setToolTip("Physical or special")

        self.crit = QPushButton("Crit", objectName="crit")
        self.crit.setCheckable(True)
        self.crit.setFixedWidth(44)
        self.crit.setToolTip("Critical hit")

        self.hidden_power = None   # (type, power) of the Pokémon using this row, for Hidden Power
        self.picker.move_changed.connect(self.reset)
        self.reset(None)

    def widgets(self) -> list:
        """Left to right, move box first."""
        return [self.picker, self.power, self.type, self.category, self.crit]

    def reset(self, move: dict | None) -> None:
        """Back to the move's normal values (called whenever a different move is picked)."""
        has = move is not None
        for w in (self.power, self.type, self.category, self.crit):
            w.setEnabled(has)
        self.crit.setChecked(False)
        if not has:
            self.power.setText("")
            self.picker.setToolTip("")
            return
        power, mtype = move["power"], move["type"]
        if move["name"] == "Hidden Power" and self.hidden_power:
            mtype, power = self.hidden_power       # this Pokémon's own Hidden Power
        self.power.setText(str(power or 0))
        self.type.setCurrentText(mtype)
        self.category.setCurrentText(move["category"])
        acc = f"{move['accuracy']}% accuracy" if move["accuracy"] else "never misses"
        self.picker.setToolTip(f"{move['name']}: {acc}, {move['pp']} PP, priority {move['priority']:+d}")

    def settings(self) -> dict | None:
        """Everything the damage formula needs about this move, or None for an empty slot."""
        move = self.picker.move()
        if move is None:
            return None
        return {"move": move, "power": int(self.power.text() or 0), "type": self.type.currentText(),
                "category": self.category.currentText(), "crit": self.crit.isChecked()}


class CalcSide(QFrame):
    """One side of the damage calculator: which Pokémon, and 4 move rows.

    The moves fill in from the Pokémon's real moves, but only when the Pokémon changes
    (or learns a move), so anything you change by hand isn't overwritten on every update.
    mirrored=True puts the move box on the right (for the foe's side).
    """

    def __init__(self, label: str, mirrored: bool = False):
        super().__init__()
        self.setObjectName("calcside")
        self.label = label
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)
        self.title = QLabel(objectName="rowname")
        self.title.setAlignment(Qt.AlignRight if mirrored else Qt.AlignLeft)
        lay.addWidget(self.title)

        grid = QGridLayout()
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)
        self.rows = [MoveRow() for _ in range(4)]
        for r, row in enumerate(self.rows):
            widgets = row.widgets()
            if mirrored:
                widgets.reverse()
            for c, w in enumerate(widgets):
                grid.addWidget(w, r, c)
        move_col = 4 if mirrored else 0
        grid.setColumnStretch(move_col, 1)           # the move box takes the spare width
        lay.addLayout(grid)
        lay.addStretch()

        self._shown = None   # (pid, real moves) last filled in
        self.show_pokemon(None)

    def show_pokemon(self, mon) -> None:
        """mon: a decoded Pokemon or a Battler (both have pid, species, level, moves)."""
        if mon is None:
            self.title.setText(f"{self.label.upper()}  ·  —")
            return
        self.title.setText(f"{self.label.upper()}  ·  {mon.species}  Lv {mon.level}")
        for row in self.rows:
            row.hidden_power = getattr(mon, "hidden_power", None)
        real = tuple(name for name, _pp in mon.moves)
        if (mon.pid, real) != self._shown:          # new Pokémon, or it learned a move
            self._shown = (mon.pid, real)
            for row, name in zip(self.rows, list(real) + [""] * 4):
                row.picker.set_move(name)
                row.reset(row.picker.move())         # also resets when the move name didn't change

    def moves(self) -> list:
        """Settings for the 4 move slots (see MoveRow.settings), None for empty slots."""
        return [row.settings() for row in self.rows]


class InfoPanel(QFrame):
    """The space between the two teams: the damage calculator."""

    def __init__(self):
        super().__init__()
        self.setObjectName("infopanel")
        self.setMinimumHeight(110)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 10, 14, 10)
        outer.addWidget(QLabel("DAMAGE CALCULATOR", objectName="section"))

        columns = QHBoxLayout()          # the two sides, side by side
        columns.setSpacing(12)
        self.you, self.foe = CalcSide("You"), CalcSide("Foe", mirrored=True)
        columns.addWidget(self.you, 1)
        columns.addWidget(self.foe, 1)
        outer.addLayout(columns, 1)

    def show_battle(self, data: dict) -> None:
        """In battle, use the Pokémon that are out; otherwise your lead and the opponent's."""
        battle = data.get("battle")
        if battle:
            you, foe = battle["you"], battle["foe"]   # live battle data (works for wild Pokémon too)
        else:
            you = _pick(data["party"], data.get("party_active"))
            foe = _pick(data["enemy"], data.get("enemy_active"))
        self.you.show_pokemon(you)
        self.foe.show_pokemon(foe)


def _pick(mons, active):
    """The active Pokémon if known, else the first one in the list (or None)."""
    if active is not None and mons[active] is not None:
        return mons[active]
    return next((m for m in mons if m is not None), None)
