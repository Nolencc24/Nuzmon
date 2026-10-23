"""Battle page: your party on top, the opponent at the bottom, the damage calculator between
(the calculator lives in damage_calc.py).

The Pokémon currently out in battle gets the big expanded card on each side.
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
