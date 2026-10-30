"""
Data sources for the window. Each has a poll() method returning
(data or None, status message or None); data is None when nothing changed.

data = {"meta": {...}, "party": [Pokemon|None x6], "enemy": [Pokemon|None x6],
        "party_active": index or None, "enemy_active": index or None,
        "battle": None outside battle, else {"id": int, "you": Battler, "foe": Battler}}

"battle" (memory mode only) comes straight from the battle data, so it also covers wild
Pokémon, and its "id" goes up by one for each new battle (handy for logging encounters).
"""

from __future__ import annotations

import os
import tempfile
import time

from .battle import BattleHP, BattleState
from .decoder import PARTY_SIZE, IncompleteDump, encrypt, parse, read_dump
from .memreader import (DS_RAM_START, ENEMY_OFFSET, PARTY_OFFSET, DesmumeMemory,
                        NotFound, find_desmume_pid)
from .samples import GEODUDE, SHINY_CUBONE, as_party


class MemorySource:
    """Reads DeSmuME's memory directly, reconnecting when needed (the default)."""

    RETRY_SECONDS = 2.0

    def __init__(self, pid: int | None = None, name_hint: str = "desmume"):
        self.fixed_pid, self.name_hint = pid, name_hint
        self.mem: DesmumeMemory | None = None
        self.next_attempt = 0.0
        self.last_shown = None
        self.battle = BattleHP()
        self.state = BattleState()

    def _connect(self):
        pid = self.fixed_pid or find_desmume_pid(self.name_hint)
        mem = DesmumeMemory(pid)
        try:
            mem.locate()
        except NotFound:
            mem.close()
            raise
        self.mem = mem

    def poll(self):
        """Returns (data or None, status message or None). data is None when nothing changed."""
        if self.mem is None:
            if time.monotonic() < self.next_attempt:
                return None, None
            try:
                self._connect()
            except NotFound as e:
                self.next_attempt = time.monotonic() + self.RETRY_SECONDS
                return None, f"{e}  Retrying…"
        try:
            snap = self.mem.snapshot()
        except OSError:
            self.mem.close()
            self.mem, self.last_shown = None, None   # DeSmuME closed or game reset: search again
            return None, "Lost DeSmuME. Searching again…"

        party = [parse(b) for b in snap["party"]]
        enemy = [parse(b) for b in snap["enemy"]]
        for m in party:
            if m is not None:   # remember the party's own values before battle HP overrides them
                m._party_sync = (m.hp, m.max_hp, m.status, tuple(pp for _, pp in m.moves))
        p0 = snap["base"] + PARTY_OFFSET - DS_RAM_START
        e0 = snap["base"] + ENEMY_OFFSET - DS_RAM_START
        skip = {o + i * PARTY_SIZE for o in (p0, e0) for i in range(6)}
        state = self.state.update(snap["ram"], party, enemy, self.battle)
        self.battle.apply(snap["ram"], [party, enemy], (state["party_active"], state["enemy_active"]), skip)
        battle = state["battle"]

        # only redraw when something visible changed
        shown = (snap["base"], tuple(snap["party"]), tuple(snap["enemy"]),
                 tuple((m.hp, m.max_hp, m.status) if m else None for m in party + enemy),
                 state["party_active"], state["enemy_active"],
                 battle and (battle["id"], battle["you"], battle["foe"]))
        if shown == self.last_shown:
            return None, None
        self.last_shown = shown
        data = {
            "meta": {"game": self.mem.game, "base": f"0x{snap['base']:08X}",
                     "source": f"DeSmuME pid {self.mem.pid}"},
            "party": party,
            "enemy": enemy,
            "party_active": state["party_active"],   # index of the Pokémon you have out, or None
            "enemy_active": state["enemy_active"],   # index of the foe's Pokémon, or None
            "battle": battle,
        }
        return data, None


class FileSource:
    """Reads the ss_dump.txt file written by tools/tracker.lua (the --lua fallback)."""

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


def write_demo_file() -> str:
    """Fake dump built from the real sample Pokémon in samples.py (for --demo)."""
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
