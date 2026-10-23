"""Battle page: your party on top, the opponent at the bottom, an info panel between.

The Pokémon currently out in battle gets the big expanded card on each side.
"""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from tracker.ui.widgets import Card, MovePicker, Row


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
        body.addWidget(self.lead, 3)   # lead card gets 3/5 of the width
        body.addLayout(rows, 2)        # the rows get 2/5
        outer.addLayout(body)

    def show_team(self, mons, active: int | None = None):
        """active: index of the Pokémon currently in battle (None outside battle)."""
        featured = active if active is not None and mons[active] is not None else 0
        self.lead.show_mon(mons[featured])
        others = [m for i, m in enumerate(mons) if i != featured]   # keep party order

        for row, m in zip(self.rows, others):
            row.show_mon(m)
        self.heading.setText(f"{self.title}  ·  IN BATTLE" if active is not None else self.title)


class CalcSide(QFrame):
    """One side of the damage calculator: which Pokémon, and 4 searchable move pickers.

    The pickers fill in with the Pokémon's real moves, but only when the Pokémon changes
    (or learns a move), so a move you pick by hand isn't overwritten on every update.
    """

    def __init__(self, label: str):
        super().__init__()
        self.setObjectName("calcside")
        self.label = label
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)
        self.title = QLabel(objectName="rowname")
        lay.addWidget(self.title)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(2)
        self.pickers, self.tags = [], []

        for i in range(4):
            picker, tag = MovePicker(), QLabel(objectName="movetag")
            picker.move_changed.connect(lambda move, tag=tag: tag.setText(self._describe(move)))
            grid.addWidget(picker, (i // 2) * 2, i % 2)        # 2 x 2 grid of pickers,
            grid.addWidget(tag, (i // 2) * 2 + 1, i % 2)       # each with a line of info under it
            self.pickers.append(picker)
            self.tags.append(tag)

        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        lay.addLayout(grid)
        lay.addStretch()
        self._shown = None   # (pid, real moves) last filled in
        self.show_pokemon(None)

    @staticmethod
    def _describe(move: dict | None) -> str:
        if not move:
            return ""
        acc = f"{move['accuracy']}%" if move["accuracy"] else "never misses"

        if move["category"] == "Status":
            return f"{move['type']} · Status · {acc}"
        
        power = move["power"] or ("varies" if not move["fixed_damage"] else "fixed")

        return f"{move['type']} · {move['category']} · {power} BP · {acc}"

    def show_pokemon(self, mon) -> None:
        """mon: a decoded Pokemon or a Battler (both have pid, species, level, moves)."""
        if mon is None:
            self.title.setText(f"{self.label.upper()}  ·  —")
            return
        
        self.title.setText(f"{self.label.upper()}  ·  {mon.species}  Lv {mon.level}")
        real = tuple(name for name, _pp in mon.moves)

        if (mon.pid, real) != self._shown:          # new Pokémon, or it learned a move
            self._shown = (mon.pid, real)
            for picker, name in zip(self.pickers, list(real) + [""] * 4):
                picker.set_move(name)

    def moves(self) -> list:
        """The 4 selected moves (move data dicts, None for empty slots)."""
        return [p.move() for p in self.pickers]


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
        self.you, self.foe = CalcSide("You"), CalcSide("Foe")
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


class BattlePage(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.setSpacing(10)
        self.party = TeamSection("Your party")
        self.info = InfoPanel()
        self.enemy = TeamSection("Opponent")
        lay.addWidget(self.party)
        lay.addWidget(self.info, 1)    # the middle panel takes up any spare height
        lay.addWidget(self.enemy)

    def update_data(self, data: dict) -> None:
        """Called by the main window whenever new game data arrives."""
        self.party.show_team(data["party"], data.get("party_active"))
        self.enemy.show_team(data["enemy"], data.get("enemy_active"))
        self.info.show_battle(data)
