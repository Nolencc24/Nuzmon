"""Reusable Pokémon widgets: the expanded Card and the thin Row. Any page can use these."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QValidator
from PySide6.QtWidgets import (QComboBox, QCompleter, QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QLineEdit, QProgressBar, QVBoxLayout)

from tracker.game import gamedata
from tracker.game.decoder import Pokemon
from tracker.game.stats import EV_MAX, EV_TOTAL_MAX, IV_MAX, nature_effect

DISPLAY_ORDER = ["HP", "Atk", "Def", "SpA", "SpD", "Spe"]  # summary-screen order


class BoundedIntValidator(QValidator):
    """Whole numbers from low to high. Unlike QIntValidator, a keystroke that would go past
    the limit is refused outright (QIntValidator lets you type e.g. 45 into a 0-31 box and
    then silently ignores Enter)."""

    def __init__(self, low: int, high: int, parent=None):
        super().__init__(parent)
        self.low, self.high = low, high

    def validate(self, text: str, pos: int):
        if text == "":
            return QValidator.State.Intermediate
        if not text.isdigit() or int(text) > self.high:
            return QValidator.State.Invalid
        if int(text) < self.low:
            return QValidator.State.Intermediate      # e.g. "0" while heading for "07"
        return QValidator.State.Acceptable


class StatEdit(QLineEdit):
    """A small numbers-only box (IVs, EVs). Emits committed(value) when you finish editing
    and the value actually changed. Live updates don't overwrite it while you're typing."""

    committed = Signal(int)

    def __init__(self, maximum: int):
        super().__init__(objectName="statedit")
        self.setValidator(BoundedIntValidator(0, maximum, self))
        self.setAlignment(Qt.AlignRight)
        self.setFixedWidth(38)
        self._value = 0
        self.editingFinished.connect(self._commit)

    def show_value(self, value: int):
        self._value = value
        if not self.hasFocus():
            self.setText(str(value))

    def _commit(self):
        text = self.text()
        if not text or int(text) == self._value:
            self.setText(str(self._value))      # empty or unchanged: put the value back
            return
        self._value = int(text)
        self.committed.emit(self._value)


class Card(QFrame):
    """One Pokémon, fully expanded. Widgets are built once and updated in place, so nothing flickers.

    wide=True lays the card out in three columns (summary | stats | moves) instead of
    one tall column, which is how the lead Pokémon is shown.
    editable=True makes the IVs (0-31) and EVs (0-252) editable; changes are reported
    with stat_edited("iv" or "ev", stat name, value).
    """

    stat_edited = Signal(str, str, int)

    def __init__(self, wide: bool = False, editable: bool = False):
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
            if editable:
                iv, ev = StatEdit(IV_MAX), StatEdit(EV_MAX)
                iv.committed.connect(lambda v, stat=stat: self.stat_edited.emit("iv", stat, v))
                ev.committed.connect(lambda v, stat=stat: self.stat_edited.emit("ev", stat, v))
                iv.setToolTip(f"{stat} IV (0-{IV_MAX})")
                ev.setToolTip(f"{stat} EVs (0-{EV_MAX})")
            else:
                iv, ev = QLabel(objectName="cell"), QLabel(objectName="cell")
            row = [QLabel(stat, objectName="cell"), QLabel(objectName="cell"), iv, ev]
            for c, lbl in enumerate(row):
                if c:
                    lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
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
            for box, value in ((iv, m.ivs[stat]), (ev, m.evs[stat])):
                if isinstance(box, StatEdit):
                    box.show_value(value)
                else:
                    box.setText(str(value))
            iv.setStyleSheet("color:#3ccf6e" if m.ivs[stat] == 31 else "color:#eb5757" if m.ivs[stat] == 0 else "")

        hp_type, hp_pow = m.hidden_power
        total = sum(m.evs.values())
        over = f"<span style='color:#eb5757'>{total}/{EV_TOTAL_MAX} (over the limit)</span>" \
            if total > EV_TOTAL_MAX else f"{total}/{EV_TOTAL_MAX}"
        self.extra.setText(f"EVs {over}  ·  Hidden Power {hp_type} {hp_pow}")
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


class SearchPicker(QComboBox):
    """A searchable dropdown: type any part of a name to filter the list.

    Only names from the list are accepted; anything else snaps back to the last valid
    choice (or, if exactly one name contains the text, that one is picked).
    Emits value_changed(name) when the selection changes ("" = nothing selected).
    """

    value_changed = Signal(str)

    def __init__(self, names: list[str], placeholder: str = "Search…", allow_empty: bool = True):
        super().__init__()
        self.names = list(names)
        self._lookup = {n.lower(): n for n in self.names}
        self.allow_empty = allow_empty
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)       # typing never adds new entries
        self.setMaxVisibleItems(14)
        if allow_empty:
            self.addItem("")
        self.addItems(self.names)

        completer = QCompleter(self.model(), self)
        completer.setFilterMode(Qt.MatchContains)      # match anywhere in the name
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        completer.setMaxVisibleItems(14)
        self.setCompleter(completer)
        self.lineEdit().setPlaceholderText(placeholder)

        self._current = ""
        self.lineEdit().editingFinished.connect(self._commit)
        self.activated.connect(lambda _index: self._commit())
        completer.activated.connect(lambda text: self._commit(text))

    def _commit(self, text: str | None = None):
        text = (self.currentText() if text is None else text).strip()
        name = self._lookup.get(text.lower(), "")
        if text and not name:
            matches = [n for n in self.names if text.lower() in n.lower()]
            name = matches[0] if len(matches) == 1 else ""
        if (text and not name) or (not name and not self.allow_empty):
            self.setEditText(self._current)            # not a valid choice: revert
            return
        self._select(name, emit=True)

    def _select(self, name: str, emit: bool):
        self.blockSignals(True)
        self.setCurrentIndex(max(self.findText(name, Qt.MatchFixedString), 0))
        self.setEditText(name)
        self.blockSignals(False)
        if name != self._current:
            self._current = name
            if emit:
                self.value_changed.emit(name)

    def set_value(self, name: str, emit: bool = True):
        """Select a name from the list ("" for none). emit=False updates silently."""
        self._select(self._lookup.get((name or "").lower(), ""), emit)

    def value(self) -> str:
        return self._current


class MovePicker(SearchPicker):
    """Searchable selector over every Gen 4 move. Emits move_changed(move dict or None)."""

    move_changed = Signal(object)

    def __init__(self):
        super().__init__(gamedata.all_move_names(), "Search moves…")
        self.value_changed.connect(lambda _name: self.move_changed.emit(self.move()))

    def set_move(self, name: str):
        self.set_value(name)

    def move(self) -> dict | None:
        """The selected move's data (type, power, category...), or None."""
        return gamedata.move_by_name(self._current) if self._current else None


class SpeciesPicker(SearchPicker):
    """Searchable selector over every Gen 4 species and stat-changing form."""

    def __init__(self):
        super().__init__(gamedata.all_species_names(), "Search Pokémon…", allow_empty=False)
