"""Reusable Pokémon widgets: the expanded Card and the thin Row. Any page can use these."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QComboBox, QCompleter, QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QProgressBar, QVBoxLayout)

from tracker.game import gamedata
from tracker.game.decoder import NATURES, Pokemon

DISPLAY_ORDER = ["HP", "Atk", "Def", "SpA", "SpD", "Spe"]  # summary-screen order
NATURE_STATS = ["Atk", "Def", "Spe", "SpA", "SpD"]          # order used by nature math


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


class MovePicker(QComboBox):
    """A searchable move selector: type any part of a name ("punch") to filter all Gen 4 moves.

    Only real move names are accepted; anything else snaps back to the last valid choice.
    Emits move_changed(move dict or None) when the selection changes.
    """

    move_changed = Signal(object)

    def __init__(self):
        super().__init__()
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)       # typing never adds new entries
        self.setMaxVisibleItems(14)
        self.addItem("")                               # blank = no move
        self.addItems(gamedata.all_move_names())

        completer = QCompleter(self.model(), self)
        completer.setFilterMode(Qt.MatchContains)      # match anywhere in the name
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        completer.setMaxVisibleItems(14)
        self.setCompleter(completer)
        self.lineEdit().setPlaceholderText("Search moves…")

        self._current = ""
        self.lineEdit().editingFinished.connect(self._commit)
        self.activated.connect(lambda _index: self._commit())
        completer.activated.connect(lambda text: self._commit(text))

    def _commit(self, text: str | None = None):
        text = (self.currentText() if text is None else text).strip()
        found = gamedata.move_by_name(text) if text else None
        if text and found is None:
            # not a move name: if exactly one move contains the text, take it; else revert
            matches = [n for n in gamedata.all_move_names() if text.lower() in n.lower()]
            found = gamedata.move_by_name(matches[0]) if len(matches) == 1 else None
            if found is None:
                self.setEditText(self._current)
                return
        self._select(found["name"] if found else "")

    def _select(self, name: str):
        self.blockSignals(True)
        self.setCurrentIndex(max(self.findText(name, Qt.MatchFixedString), 0))
        self.setEditText(name)
        self.blockSignals(False)
        if name != self._current:
            self._current = name
            self.move_changed.emit(self.move())

    def set_move(self, name: str):
        """Select a move by name ("" for none)."""
        found = gamedata.move_by_name(name) if name else None
        self._select(found["name"] if found else "")

    def move(self) -> dict | None:
        """The selected move's data (type, power, category...), or None."""
        return gamedata.move_by_name(self._current) if self._current else None
