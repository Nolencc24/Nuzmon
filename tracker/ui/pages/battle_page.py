"""Battle page: your party on top, the opponent at the bottom, the damage calculator between
(the calculator lives in damage_calc.py).

The big expanded card on each side shows whatever that side of the calculator is set to:
by default the Pokémon that's out (or the party lead); once you change something in the
calculator, whatever you picked there, until you press that side's Reset.
"""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from tracker.ui.pages.damage_calc import InfoPanel
from tracker.ui.widgets import Card, Row


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
        self.lead = Card(wide=True, editable=True)   # IVs/EVs editable (sent to the calculator)
        rows = QVBoxLayout()
        rows.setSpacing(4)
        self.rows = [Row() for _ in range(5)]
        for r in self.rows:
            rows.addWidget(r)
        rows.addStretch()
        body.addWidget(self.lead, 3)   # lead card gets 3/5 of the width...
        body.addLayout(rows, 2)        # ...the rows get 2/5
        outer.addLayout(body)

    def show_team(self, mons, active: int | None = None, featured=None, in_battle: bool = False,
                  pinned: bool = False):
        """mons: the 6 party slots. active: index of the Pokémon out in battle, or None.
        featured: Pokémon for the big card (may be a level-adjusted copy, a preview, or a
        wild Pokémon not in mons); None = the active one, or slot 1."""
        if featured is None:
            index = active if active is not None and mons[active] is not None else 0
            featured = mons[index]
        else:
            # if the featured Pokémon is a team member, it moves out of the rows; otherwise it
            # takes the place of whoever is out (or the lead)
            index = None if featured.preview else next(
                (i for i, m in enumerate(mons) if m is not None and m.pid == featured.pid), None)
            if index is None:
                index = active if active is not None else 0
        self.lead.show_mon(featured)
        others = [m for i, m in enumerate(mons) if i != index]   # keep party order
        for row, m in zip(self.rows, others):
            row.show_mon(m)
        heading = self.title + ("  ·  IN BATTLE" if in_battle or active is not None else "")
        if featured is not None and featured.preview:
            heading += "  ·  PREVIEW (You Edited Stats  )"
        elif pinned:
            heading += "  ·  PREVIEW (You Edited Stats)"
        self.heading.setText(heading)


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

        self.data = None
        # editing species/level/moves in the calculator redraws the big cards right away
        self.info.you.subject_changed.connect(self._render)
        self.info.foe.subject_changed.connect(self._render)
        # IV/EV edits in a big card change that side of the calculator
        self.party.lead.stat_edited.connect(self.info.you.set_stat)
        self.enemy.lead.stat_edited.connect(self.info.foe.set_stat)

    def update_data(self, data: dict) -> None:
        """Called by the main window whenever new game data arrives."""
        self.data = data
        self.info.show_battle(data)
        self._render()

    def _render(self) -> None:
        data = self.data
        if data is None:
            return
        battle = data.get("battle") is not None
        enemy = data["enemy"]
        if battle and data.get("enemy_active") is None:
            enemy = [None] * 6           # wild battle: the opponent list is left over from an old battle
        you, foe = self.info.you, self.info.foe
        self.party.show_team(data["party"], data.get("party_active"), you.subject(), battle, you.pinned)
        self.enemy.show_team(enemy, data.get("enemy_active"), foe.subject(), battle, foe.pinned)
