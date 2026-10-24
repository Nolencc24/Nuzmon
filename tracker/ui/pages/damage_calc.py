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
from tracker.game.stats import (adjusted, form_name, from_battler, preview, speed, status_kind, with_hp,
                                with_status)
from tracker.ui.widgets import BoundedIntValidator, MovePicker, SpeciesPicker

CATEGORIES = ["Physical", "Special", "Status"]
STAGE_STATS = ["Atk", "Def", "SpA", "SpD", "Spe"]
STAGE_TEXT = [f"{v:+d}" if v else "0" for v in range(6, -7, -1)]   # "+6" ... "0" ... "-6"; index = 6 - stage


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

        # stat stages: Atk [ 0 ]  Def [ 0 ] ... (follow the battle, or pick by hand)
        stage_row = QHBoxLayout()
        stage_row.setSpacing(4)
        if mirrored:
            stage_row.addStretch()
        self.stage_boxes = {}
        for stat in STAGE_STATS:
            box = QComboBox(objectName="stage")
            box.addItems(STAGE_TEXT)
            box.activated.connect(lambda _index, stat=stat: self._on_stage(stat))   # your picks only
            stage_row.addWidget(QLabel(stat, objectName="movetag"))
            stage_row.addWidget(box)
            stage_row.addSpacing(6)
            self.stage_boxes[stat] = box
        if not mirrored:
            stage_row.addStretch()
        lay.addLayout(stage_row)
        lay.addStretch()

        self.live = None              # the Pokémon that's actually out (or leading)
        self.team = []                # this side's party, for matching picked species
        self.pinned = False           # True once you change something; Reset clears it
        self.pin_pid = None           # pinned real Pokémon (its PID), or None for a preview
        self.pin_slot = None          # ...and its index in self.team (twins share a PID)
        self.pin_snapshot = None      # last seen copy of it (used if it's not in the team list)
        self.pin_species = None       # pinned preview species, when pin_pid is None
        self.level_override = None    # level typed by hand, or None
        self.iv_override = {}         # IVs edited by hand (in the big card), e.g. {"Spe": 31}
        self.ev_override = {}         # EVs edited by hand
        self.hp_override = None       # (current HP, max HP it was typed against), or None
        self.nature_override = None   # nature picked by hand (in the big card), or None
        self.status_override = None   # status picked by hand (one of stats.STATUSES), or None
        self.stage_override = {}      # stat stages picked by hand, e.g. {"Atk": 2}
        self.battler = None           # this side's live Battler in battle (has the stat stages), or None
        self.active = None            # party index of the Pokémon that's out, or None
        self._filled = None           # identity of the Pokémon whose moves are in the rows
        self._filling = False         # True while the side fills its own rows (not your edits)

        self.species.value_changed.connect(self._on_species)
        self.level.editingFinished.connect(self._on_level)
        self._sync()

    # ---- what this side is about

    def set_live(self, live, team, battler=None, active: int | None = None) -> None:
        """Called on every update with the live Pokémon (or None) and this side's team.
        In battle also with this side's Battler and the party index of the one that's out."""
        self.team = list(team)
        self.live = live
        self.battler, self.active = battler, active
        self._sync()

    def stages(self) -> dict:
        """Stat stages (-6..+6) for Atk, Def, SpA, SpD, Spe: picked by hand, else the live
        battle's if this side's Pokémon is the one out, else 0."""
        live = self._live_stages()
        return {s: self.stage_override.get(s, live.get(s, 0)) for s in STAGE_STATS}

    def slot(self) -> int | None:
        """Index in this side's team of the Pokémon subject() is based on, or None (a
        preview or a wild Pokémon). Needed because twins share a PID (see game/battle.py)."""
        base = self._base()
        return next((i for i, m in enumerate(self.team) if m is not None and m is base), None)

    def subject(self):
        """The Pokémon this side calculates with (live, pinned, or a preview), at the chosen
        level. None if there's nothing to show."""
        base = self._base()
        if base is None:
            return None
        mon = adjusted(base, self.level_override, self.iv_override, self.ev_override, self.nature_override)
        if self.hp_override is not None:
            mon = with_hp(mon, *self.hp_override)
        if self.status_override is not None:
            mon = with_status(mon, self.status_override)
        return mon

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

    def set_hp(self, hp: int) -> None:
        """Change current HP (typed in the big card). Pins this side, like any other edit.
        If the max HP changes later (e.g. a new level), the HP keeps its percentage."""
        current = self.subject()
        if current is None or current.hp == hp:
            return
        self._pin()
        self.hp_override = (hp, current.max_hp)
        self._sync()
        self.subject_changed.emit()

    def set_nature(self, nature: str) -> None:
        """Change the nature (picked in the big card). Pins this side, like any other edit."""
        current = self.subject()
        if current is None or current.nature == nature:
            return
        self._pin()
        self.nature_override = nature
        self._sync()
        self.subject_changed.emit()

    def set_status(self, status: str) -> None:
        """Change the status condition (picked in the big card). Pins this side, like any
        other edit. The damage calculator will use it later (burn, poison damage...)."""
        current = self.subject()
        if current is None or status_kind(current.status) == status:
            return
        self._pin()
        self.status_override = status
        self._sync()
        self.subject_changed.emit()

    def select(self, mon) -> None:
        """Calculate with this team member (clicked in the Battle tab), with its own level,
        IVs, EVs, HP and nature. Pins this side, like any other edit."""
        if mon is None or mon.preview:
            return
        self._pin()
        self._pin_to(mon)
        self.level_override = None
        self.iv_override, self.ev_override = {}, {}
        self.hp_override = self.nature_override = self.status_override = None
        self.stage_override = {}
        self._sync()
        self.subject_changed.emit()

    def reset(self) -> None:
        """Forget everything picked by hand and follow the live Pokémon again."""
        self.pinned = False
        self.pin_pid = self.pin_slot = self.pin_snapshot = self.pin_species = None
        self.level_override = None
        self.iv_override, self.ev_override = {}, {}
        self.hp_override = self.nature_override = self.status_override = None
        self.stage_override = {}
        self._filled = None            # refill the moves from the live Pokémon
        self._sync()
        self.subject_changed.emit()

    # ---- internals

    def _live_stages(self) -> dict:
        """The battle's stat stages, if this side's Pokémon is the one out; else {}."""
        b, base = self.battler, self._base()
        if b is None or base is None or base.preview or base.pid != b.pid:
            return {}
        slot = self.slot()
        if slot is not None and self.active is not None and slot != self.active:
            return {}                    # a twin (same PID) that isn't the one out
        return b.stages

    def _on_stage(self, stat: str):
        self._pin()
        self.stage_override[stat] = 6 - self.stage_boxes[stat].currentIndex()
        self._sync()
        self.subject_changed.emit()

    def _base(self):
        if not self.pinned:
            return self.live
        if self.pin_pid is not None:
            # same party slot if it still holds this PID (twins share one), else by PID
            current = self.team[self.pin_slot] if self.pin_slot is not None and self.pin_slot < len(self.team) else None
            if current is None or current.pid != self.pin_pid:
                current = next((m for m in self.team + [self.live] if m is not None and m.pid == self.pin_pid), None)
            if current is not None:
                self.pin_snapshot = current          # fresh data (live HP) when available
            return self.pin_snapshot
        level = self.level_override or 50
        return preview(self.pin_species, level, self._picked_moves())

    def _pin_to(self, mon):
        """Pin this real Pokémon (an object from self.team, or the live one)."""
        self.pin_pid, self.pin_snapshot, self.pin_species = mon.pid, mon, None
        self.pin_slot = next((i for i, m in enumerate(self.team) if m is mon), None)

    def _identity(self):
        if self.pinned:
            return ("pinned", self.pin_pid, self.pin_slot, self.pin_species)
        if self.live is None:
            return None
        return (self.live.pid, tuple(name for name, _pp in self.live.moves))

    def _pin(self):
        """Stop following the game, keeping whatever is shown now."""
        if self.pinned:
            return
        base = self._base()               # read before pinning: it's the live one
        self.pinned = True
        if base is not None and not base.preview:
            self._pin_to(base)
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
        self.iv_override, self.ev_override = {}, {}     # a different Pokémon: its own IVs/EVs/HP/nature
        self.hp_override = self.nature_override = self.status_override = None
        self.stage_override = {}
        real = next((m for m in self.team + [self.live] if m is not None and form_name(m) == name), None)
        if real is not None:                       # your own Pokémon: use the real one
            self._pin_to(real)
            self.level_override = None
        else:                                      # anything else: a preview
            self.pin_pid = self.pin_slot = self.pin_snapshot = None
            self.pin_species = name
            self.level_override = self.level_override or (previous.level if previous and previous.level else 50)
        self._sync()
        self.subject_changed.emit()

    def _on_level(self):
        # Qt reports "editing finished" on every focus loss (even while closing), so only
        # act when the level really changed.
        text = self.level.text()
        self.level.setModified(False)     # typing is done: live updates may show the level again
        current = self.subject()
        if not text or current is None or int(text) == current.level:
            self.level.setText(str(current.level) if current is not None and current.level else "")
            return
        self.set_level(int(text))

    def set_level(self, level: int) -> None:
        """Change the level (typed here or in the big card); stats scale with it. Pins this
        side, like any other edit."""
        current = self.subject()
        level = max(1, min(100, level))
        if current is None or level == current.level:
            return
        self._pin()
        base = self._base()
        self.level_override = None if base is not None and level == base.level and not base.preview else level
        self._sync()
        self.subject_changed.emit()

    def _sync(self):
        """Update the header and (if the Pokémon changed) the move rows to match subject()."""
        subj = self.subject()
        self.species.set_value(form_name(subj) if subj else "", emit=False)
        if not self.level.isModified():   # don't overwrite a level you're still typing
            self.level.setText(str(subj.level) if subj is not None and subj.level else "")
        self.level.setEnabled(subj is not None)
        self.reset_button.setEnabled(self.pinned)
        self.title.setToolTip("Pinned: not following the game. Press Reset to follow it again."
                              if self.pinned else "Following the Pokémon that's out")

        stages = self.stages()
        for stat, box in self.stage_boxes.items():
            value = stages[stat]
            if box.currentIndex() != 6 - value:
                box.setCurrentIndex(6 - value)
            box.setEnabled(subj is not None)
            box.setStyleSheet("color:#3ccf6e" if value > 0 else "color:#eb5757" if value < 0 else "")

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
        header = QHBoxLayout()
        header.addWidget(QLabel("DAMAGE CALCULATOR", objectName="section"))
        header.addStretch()
        self.speed = QLabel(objectName="speed")      # which side moves first

        header.addWidget(self.speed)
        outer.addLayout(header)

        columns = QHBoxLayout()          # the two sides, side by side
        columns.setSpacing(12)
        self.you, self.foe = CalcSide("You"), CalcSide("Foe", mirrored=True)
        columns.addWidget(self.you, 1)
        columns.addWidget(self.foe, 1)
        outer.addLayout(columns, 1)

        self.data = None
        self.you.subject_changed.connect(self._show_speed)
        self.foe.subject_changed.connect(self._show_speed)

    def _show_speed(self) -> None:
        """Compare the two sides' Pokémon (live, pinned or previews alike)."""
        you, foe = self.you.subject(), self.foe.subject()
        if you is None or foe is None:
            self.speed.setText("")
            return
        speeds = []
        for side, mon in ((self.you, you), (self.foe, foe)):
            stage = side.stages()["Spe"]
            text = str(speed(mon, stage))
            if stage:
                text += f" ({stage:+d})"
            if status_kind(mon.status) == "Paralyzed":
                text += " (PAR)"
            speeds.append((speed(mon, stage), text))
        (mine, mine_text), (theirs, theirs_text) = speeds
        if mine > theirs:
            verdict, color = "You move first", "#3ccf6e"
        elif mine < theirs:
            verdict, color = "Foe moves first", "#eb5757"
        else:
            verdict, color = "Speed tie (random)", "#f2c94c"
        self.speed.setText(f"Speed  You {mine_text}  vs  Foe {theirs_text}   ·   "
                           f"<span style='color:{color}; font-weight:600'>{verdict}</span>")

    def show_battle(self, data: dict) -> None:
        """In battle, use the Pokémon that are out; otherwise your lead and the opponent's."""
        self.data = data
        party, enemy = data["party"], data["enemy"]
        battle = data.get("battle")
        if battle:
            # by party index, not PID: a trainer's identical Pokémon share one PID
            pa, ea = data.get("party_active"), data.get("enemy_active")
            you = party[pa] if pa is not None else from_battler(battle["you"])
            foe = enemy[ea] if ea is not None else None
            foe_team = enemy
            if foe is None:              # not in the opponent's party: a wild Pokémon
                foe, foe_team = from_battler(battle["foe"]), []
        else:
            you = _pick(party, data.get("party_active"))
            foe = _pick(enemy, data.get("enemy_active"))
            foe_team = enemy
        battle = battle or {}
        self.you.set_live(you, party, battle.get("you"), data.get("party_active"))
        self.foe.set_live(foe, foe_team, battle.get("foe"), data.get("enemy_active"))
        self._show_speed()


def _pick(mons, active):
    """The active Pokémon if known, else the first one in the list (or None)."""
    if active is not None and mons[active] is not None:
        return mons[active]
    return next((m for m in mons if m is not None), None)
