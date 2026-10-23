"""
Battle tracking: live HP and which Pokémon are currently out.

Layouts come from the pret/pokeheartgold decompilation:
  * BattleMon: the in-battle copy of each active Pokémon (HP is updated here during battle)
  * battleMons[4]: [you, foe, your partner, foe's partner] (partners only in doubles)
  * a battle-only copy of each party, where a switched-out Pokémon's HP is saved
The real party is only updated when the battle ends.
"""

from __future__ import annotations

import struct
import time

from .decoder import PARTY_SIZE, _status_text, parse

BM_SPECIES, BM_LEVEL, BM_HP, BM_MAX_HP, BM_PID, BM_STATUS = 0x00, 0x34, 0x4C, 0x50, 0x68, 0x6C
BM_PP = 0x2C
BM_SIZE = 0xC0   # battleMons[4]: [you, foe, your partner, foe's partner] (partners only in doubles)


class BattleHP:
    """Finds the in-battle copy of each Pokémon and decides which HP value is current.

    Battle copies linger in memory after a battle ends, and a new battle may create a
    fresh copy elsewhere. So for each Pokémon we track every copy (the party entry plus
    any battle copies) and show whichever one changed most recently.
    """

    def __init__(self):
        self.seen = {}    # pid -> {"party" or RAM offset: (value, time it last changed)}
        self.first_poll = True

    @staticmethod
    def _matches(ram: bytes, off: int, mon) -> bool:
        if off < 0 or off % 4 or off + 0x70 > len(ram):
            return False
        
        species = struct.unpack_from("<H", ram, off + BM_SPECIES)[0]
        hp, max_hp = struct.unpack_from("<iI", ram, off + BM_HP)

        return species == mon.species_id and 0 < max_hp <= 999 and 0 <= hp <= max_hp

    def find_all(self, ram: bytes, mon) -> list[int]:
        """RAM offsets of every battle copy of this Pokémon (matched by PID + species)."""
        key = struct.pack("<I", mon.pid)
        found, i = [], ram.find(key)

        while i != -1:
            if self._matches(ram, i - BM_PID, mon):
                found.append(i - BM_PID)
            i = ram.find(key, i + 1)

        return found

    @staticmethod
    def find_party_copies(ram: bytes, mon, skip=()) -> list[int]:
        """RAM offsets of other full Pokémon entries with this PID, e.g. the battle-only copy
        of the party the game makes at the start of a battle. When a Pokémon is switched
        out, its HP is saved there (the real party is only updated when the battle ends)."""
        key = struct.pack("<I", mon.pid)
        found, i = [], ram.find(key)

        while i != -1:
            if i % 4 == 0 and i not in skip and i + PARTY_SIZE <= len(ram):
                copy = parse(ram[i:i + PARTY_SIZE])
                if copy is not None and copy.species_id == mon.species_id and copy.hp is not None:
                    found.append(i)

            i = ram.find(key, i + 1)

        return found

    def apply(self, ram: bytes, mons, skip=()) -> None:
        """skip: RAM offsets of the real party/enemy entries (already read as "party")."""
        now = time.monotonic()
        for mon in mons:
            if mon is None or mon.hp is None:
                continue

            rec = self.seen.setdefault(mon.pid, {})
            values = {"party": (mon.hp, mon.max_hp, mon.status)}

            for off in self.find_all(ram, mon):
                hp, max_hp = struct.unpack_from("<iI", ram, off + BM_HP)
                status = _status_text(struct.unpack_from("<I", ram, off + BM_STATUS)[0] & 0xFF)
                values[("battler", off)] = (hp, max_hp, status)

            for off in self.find_party_copies(ram, mon, skip):
                copy = parse(ram[off:off + PARTY_SIZE])
                values[("copy", off)] = (copy.hp, copy.max_hp, copy.status)

            for key, val in values.items():
                if key not in rec:
                    # Anything already in memory when the tracker starts counts as "old"
                    # (party slightly newer than battle copies), so a leftover copy from an
                    # earlier battle can't win. Copies that appear later are new.
                    if self.first_poll:
                        rec[key] = (val, -1.0 if key == "party" else -2.0)

                    else:
                        rec[key] = (val, now if key != "party" else now - 1e-6)

                elif rec[key][0] != val:
                    rec[key] = (val, now)

            for key in [k for k in rec if k not in values]:
                del rec[key]   # that copy is gone or was overwritten

            newest = max(rec, key=lambda k: rec[k][1])
            if newest != "party":
                mon.hp, mon.max_hp, mon.status = rec[newest][0]
                mon.stats["HP"] = mon.max_hp
                mon.in_battle = True

        self.first_poll = False


class BattleState:
    """Works out which Pokémon are currently out in battle.

    The game keeps the active battlers in an array: battleMons[0] is yours, [1] the foe's.
    Switching overwrites that slot. The array stays in memory after the battle, so a battle
    counts as over once your active Pokémon's party entry (HP, status, PP, which the game
    writes back when a battle ends) has changed more recently than the array.
    """

    def __init__(self):
        self.arrays = {}   # RAM offset -> (signature, time it last changed)
        self.party = {}    # pid -> (sync values, time they last changed)
        self.first_poll = True

    @staticmethod
    def _valid(ram: bytes, off: int) -> bool:
        if off < 0 or off + BM_SIZE > len(ram):
            return False
        species = struct.unpack_from("<H", ram, off + BM_SPECIES)[0]
        hp, max_hp = struct.unpack_from("<iI", ram, off + BM_HP)
        return 1 <= species <= 493 and 1 <= ram[off + BM_LEVEL] <= 100 and 0 < max_hp <= 999 and 0 <= hp <= max_hp

    @staticmethod
    def _signature(ram: bytes, base: int):
        return tuple(ram[base + i * BM_SIZE: base + (i + 1) * BM_SIZE] for i in range(2))

    def update(self, ram: bytes, party, enemy, finder: BattleHP):
        """Returns (index of your active Pokémon, index of the foe's), or (None, None)."""
        now = time.monotonic()

        for mon in party:
            if mon is None or mon.hp is None:
                continue
            # values straight from the party data (not the battle-adjusted ones)
            vals = getattr(mon, "_party_sync")
            old = self.party.get(mon.pid)
            if old is None:
                self.party[mon.pid] = (vals, -1.0 if self.first_poll else now - 1e-6)
            elif old[0] != vals:
                self.party[mon.pid] = (vals, now)

        # Candidate arrays: anywhere one of your Pokémon sits in slot 0 (or slot 2 in doubles)
        # with another valid battler right after it.
        found = set()
        for mon in party:
            if mon is None:
                continue

            for off in finder.find_all(ram, mon):
                for base in (off, off - 2 * BM_SIZE):
                    if base >= 0 and base % 4 == 0 and self._valid(ram, base) and self._valid(ram, base + BM_SIZE):
                        found.add(base)

        for base in list(self.arrays):
            if base not in found:
                del self.arrays[base]

        for base in found:
            sig = self._signature(ram, base)
            old = self.arrays.get(base)
            if old is None:   # leftovers present at startup are old; anything later is a new battle
                self.arrays[base] = (sig, -2.0 if self.first_poll else now)

            elif old[0] != sig:
                self.arrays[base] = (sig, now)

        self.first_poll = False

        if not self.arrays:
            return None, None

        base = max(self.arrays, key=lambda b: self.arrays[b][1])
        changed = self.arrays[base][1]
        my_pid = struct.unpack_from("<I", ram, base + BM_PID)[0]
        foe_pid = struct.unpack_from("<I", ram, base + BM_SIZE + BM_PID)[0]
        
        if my_pid in self.party and self.party[my_pid][1] > changed:
            return None, None   # party updated after the battle data: battle is over

        index = lambda mons, pid: next((i for i, m in enumerate(mons) if m and m.pid == pid), None)
        return index(party, my_pid), index(enemy, foe_pid)
