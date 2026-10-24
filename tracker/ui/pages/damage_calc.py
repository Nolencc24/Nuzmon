"""The damage calculator in the middle of the Battle tab.

    InfoPanel           the whole calculator: a "You" side and a "Foe" side
      CalcSide          one side: species + level, then 4 move rows
        MoveRow         move | base power | type | physical/special | crit

The foe's side is mirrored, so each side's move boxes sit along the panel's outer edge.

Each side follows the Pokémon that's out (live). Changing anything on a side (species,
level, a move or its settings) pins that side: it stops following the game until you
press its Reset button. The side's current Pokémon (CalcSide.subject()) is also what the
Battle tab shows in the big card.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QVBoxLayout)

from tracker.game import gamedata
from tracker.game.stats import adjusted, form_name, from_battler, preview
from tracker.ui.widgets import BoundedIntValidator, MovePicker, SpeciesPicker

CATEGORIES = ["Physical", "Special", "Status"]


class MoveRow:
    """One move slot and its adjustable settings. Not a widget itself: the widgets are
    placed into the side's grid so every row's columns line up."""

    def __init__(self):
        self.picker = MovePicker()

        self.power = QLineEdit(objectName="power")   # editable base power (numbers 0-999 only)
        self.power.setValidator(BoundedIntValidator(0, 999, self.power))
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
            self.type.setCurrentIndex(-1)        # blank, not a leftover value
            self.category.setCurrentIndex(-1)
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
    """One side of the damage calculator: species + level + Reset, then 4 move rows.

    Follows the live Pokémon until you change something; then the side is pinned:
      * a real Pokémon (the live one, or a team member you picked) stays selected even if
        it switches out, with its live HP still updating
      * any other species is a preview (IVs 31, EVs 0, neutral nature)
      * your moves, level and move settings are kept
    Reset goes back to following the live Pokémon.

    mirrored=True lays the side out right-to-left (for the foe).
    Emits subject_changed whenever subject() may have changed.
    """

    subject_changed = Signal()

    def __init__(self, label: str, mirrored: bool = False):
        super().__init__()
        self.setObjectName("calcside")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)

        header = QHBoxLayout()
        header.setSpacing(6)
        self.title = QLabel(label.upper(), objectName="rowname")
        self.species = SpeciesPicker()
        self.species.setToolTip("Pick any Pokémon to calculate with (and show in the big card)")
        level_label = QLabel("Lv", objectName="dim")
        self.level = QLineEdit(objectName="power")
        self.level.setValidator(BoundedIntValidator(1, 100, self.level))
        self.level.setAlignment(Qt.AlignCenter)
        self.level.setFixedWidth(40)
        self.level.setToolTip("Level (stats scale with it)")
        self.reset_button = QPushButton("Reset", objectName="reset")
        self.reset_button.setToolTip("Go back to the Pokémon that's out in the game")
        self.reset_button.clicked.connect(self.reset)
        items = [self.title, self.species, level_label, self.level, self.reset_button]
        if mirrored:
            items.reverse()
        for w in items:
            header.addWidget(w, 1 if w is self.species else 0)
        lay.addLayout(header)

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
            # any change you make to a move row pins this side
            row.picker.move_changed.connect(self._on_move_edit)
            row.power.textEdited.connect(self._on_move_edit)
            row.type.activated.connect(self._on_move_edit)
            row.category.activated.connect(self._on_move_edit)
            row.crit.clicked.connect(self._on_move_edit)
        move_col = 4 if mirrored else 0
        grid.setColumnStretch(move_col, 1)           # the move box takes the spare width
        lay.addLayout(grid)
        lay.addStretch()

        self.live = None              # the Pokémon that's actually out (or leading)
        self.team = []                # this side's party, for matching picked species
        self.pinned = False           # True once you change something; Reset clears it
        self.pin_pid = None           # pinned real Pokémon (its PID), or None for a preview
        self.pin_snapshot = None      # last seen copy of it (used if it's not in the team list)
        self.pin_species = None       # pinned preview species, when pin_pid is None
        self.level_override = None    # level typed by hand, or None
        self.iv_override = {}         # IVs edited by hand (in the big card), e.g. {"Spe": 31}
        self.ev_override = {}         # EVs edited by hand
        self._filled = None           # identity of the Pokémon whose moves are in the rows
        self._filling = False         # True while the side fills its own rows (not your edits)

        self.species.value_changed.connect(self._on_species)
        self.level.editingFinished.connect(self._on_level)
        self._sync()

    # ---- what this side is about

    def set_live(self, live, team) -> None:
        """Called on every update with the live Pokémon (or None) and this side's team."""
        self.team = [m for m in team if m is not None]
        self.live = live
        self._sync()

    def subject(self):
        """The Pokémon this side calculates with (live, pinned, or a preview), at the chosen
        level. None if there's nothing to show."""
        base = self._base()
        if base is None:
            return None
        return adjusted(base, self.level_override, self.iv_override, self.ev_override)

    def moves(self) -> list:
        """Settings for the 4 move slots (see MoveRow.settings), None for empty slots."""
        return [row.settings() for row in self.rows]

    def set_stat(self, kind: str, stat: str, value: int) -> None:
        """Change one IV (kind "iv") or EV (kind "ev"). Pins this side, like any other edit."""
        current = self.subject()
        if current is None or (current.ivs if kind == "iv" else current.evs)[stat] == value:
            return
        self._pin()
        (self.iv_override if kind == "iv" else self.ev_override)[stat] = value
        self._sync()
        if kind == "iv":                # IVs decide Hidden Power's type and power
            for row in self.rows:
                move = row.picker.move()
                if move and move["name"] == "Hidden Power":
                    row.reset(move)
        self.subject_changed.emit()

    def reset(self) -> None:
        """Forget everything picked by hand and follow the live Pokémon again."""
        self.pinned = False
        self.pin_pid = self.pin_snapshot = self.pin_species = None
        self.level_override = None
        self.iv_override, self.ev_override = {}, {}
        self._filled = None            # refill the moves from the live Pokémon
        self._sync()
        self.subject_changed.emit()

    # ---- internals

    def _base(self):
        if not self.pinned:
            return self.live
        if self.pin_pid is not None:
            current = next((m for m in self.team + [self.live] if m is not None and m.pid == self.pin_pid), None)
            if current is not None:
                self.pin_snapshot = current          # fresh data (live HP) when available
            return self.pin_snapshot
        level = self.level_override or 50
        return preview(self.pin_species, level, self._picked_moves())

    def _identity(self):
        if self.pinned:
            return ("pinned", self.pin_pid, self.pin_species)
        if self.live is None:
            return None
        return (self.live.pid, tuple(name for name, _pp in self.live.moves))

    def _pin(self):
        """Stop following the game, keeping whatever is shown now."""
        if self.pinned:
            return
        current = self.subject()
        self.pinned = True
        if current is not None and not current.preview:
            self.pin_pid, self.pin_snapshot = current.pid, self._base()
        self._filled = self._identity()   # keep the moves that are in the rows now

    def _picked_moves(self) -> list:
        return [(m["name"], m["pp"]) for m in (row.picker.move() for row in self.rows) if m]

    def _on_move_edit(self, *_args):
        if self._filling:
            return
        self._pin()
        self._sync()
        self.subject_changed.emit()

    def _on_species(self, name: str):
        previous = self.subject()
        self._pin()
        self.iv_override, self.ev_override = {}, {}     # a different Pokémon: its own IVs/EVs
        real = next((m for m in self.team + [self.live] if m is not None and form_name(m) == name), None)
        if real is not None:                       # your own Pokémon: use the real one
            self.pin_pid, self.pin_snapshot, self.pin_species = real.pid, real, None
            self.level_override = None
        else:                                      # anything else: a preview
            self.pin_pid, self.pin_snapshot, self.pin_species = None, None, name
            self.level_override = self.level_override or (previous.level if previous and previous.level else 50)
        self._sync()
        self.subject_changed.emit()

    def _on_level(self):
        # Qt reports "editing finished" on every focus loss (even while closing), so only
        # act when the level really changed.
        text = self.level.text()
        current = self.subject()
        if not text or current is None or int(text) == current.level:
            self.level.setText(str(current.level) if current is not None and current.level else "")
            return
        level = max(1, min(100, int(text)))
        self._pin()
        base = self._base()
        self.level_override = None if base is not None and level == base.level and not base.preview else level
        self._sync()
        self.subject_changed.emit()

    def _sync(self):
        """Update the header and (if the Pokémon changed) the move rows to match subject()."""
        subj = self.subject()
        self.species.set_value(form_name(subj) if subj else "", emit=False)
        self.level.setText(str(subj.level) if subj is not None and subj.level else "")
        self.level.setEnabled(subj is not None)
        self.reset_button.setEnabled(self.pinned)
        self.title.setToolTip("Pinned: not following the game. Press Reset to follow it again."
                              if self.pinned else "Following the Pokémon that's out")

        hp = subj.hidden_power if subj is not None else None
        for row in self.rows:
            row.hidden_power = hp
        ident = self._identity()
        if ident != self._filled:     # a different Pokémon: refill the moves
            self._filled = ident
            names = [] if subj is None or subj.preview else [name for name, _pp in subj.moves]
            self._filling = True
            try:
                for row, name in zip(self.rows, names + [""] * 4):
                    row.picker.set_move(name)
                    row.reset(row.picker.move())
            finally:
                self._filling = False


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
        party, enemy = data["party"], data["enemy"]
        battle = data.get("battle")
        if battle:
            you = _by_pid(party, battle["you"].pid) or from_battler(battle["you"])
            foe = _by_pid(enemy, battle["foe"].pid)
            foe_team = enemy
            if foe is None:              # not in the opponent's party: a wild Pokémon
                foe, foe_team = from_battler(battle["foe"]), []
        else:
            you = _pick(party, data.get("party_active"))
            foe = _pick(enemy, data.get("enemy_active"))
            foe_team = enemy
        self.you.set_live(you, party)
        self.foe.set_live(foe, foe_team)


def _by_pid(mons, pid):
    return next((m for m in mons if m is not None and m.pid == pid), None)


def _pick(mons, active):
    """The active Pokémon if known, else the first one in the list (or None)."""
    if active is not None and mons[active] is not None:
        return mons[active]
    return next((m for m in mons if m is not None), None)
