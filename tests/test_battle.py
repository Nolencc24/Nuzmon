"""Checks battle tracking for "twins": a trainer's Pokémon of the same species and level,
which share one PID. Run:  python tests/test_battle.py"""

import dataclasses
import os
import struct
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # project folder

from tracker.game.battle import BM_HP, BM_PID, BM_SPECIES, BattleHP, BattleState
from tracker.game.decoder import encrypt, parse
from tracker.game.samples import GEODUDE, SHINY_CUBONE, as_party


def test():
    geo = parse(encrypt(as_party(GEODUDE, 14, 37, 37)))
    cub = parse(encrypt(as_party(SHINY_CUBONE, 9, 28, 28)))
    twins = [dataclasses.replace(geo, stats=dict(geo.stats)) for _ in range(3)]   # 3 x same PID

    # which twin is out: the first, until it faints; then the next one
    state = BattleState()
    foe = lambda hp: SimpleNamespace(pid=geo.pid, hp=hp)
    assert state._active(1, twins, foe(37)) == 0
    assert state._active(1, twins, foe(10)) == 0
    assert state._active(1, twins, foe(0)) == 0          # fainted, still lying there
    assert state._active(1, twins, foe(0)) == 0
    assert state._active(1, twins, foe(37)) == 1         # the next twin came out
    assert state._active(1, twins, foe(20)) == 1
    assert state._active(1, twins, foe(0)) == 1
    assert state._active(1, twins, foe(37)) == 2
    # a different Pokémon in between doesn't lose track of who fainted
    state = BattleState()
    team = [twins[0], cub, twins[1]]
    assert state._active(1, team, foe(0)) == 0
    assert state._active(1, team, SimpleNamespace(pid=cub.pid, hp=28)) == 1
    assert state._active(1, team, foe(37)) == 2
    # a twin whose stored HP is already 0 is skipped (e.g. tracker started mid-battle)
    state = BattleState()
    fainted_first = [dataclasses.replace(twins[0], hp=0)] + twins[1:]
    assert state._active(1, fainted_first, foe(37)) == 1
    # Pokémon with their own PID are found by PID as before
    assert BattleState()._active(0, [cub, geo], SimpleNamespace(pid=geo.pid, hp=5)) == 1

    # live battle HP only goes to the twin that's out
    ram = bytearray(0x1000)
    off = 0x200
    struct.pack_into("<H", ram, off + BM_SPECIES, geo.species_id)
    struct.pack_into("<iI", ram, off + BM_HP, 12, 37)
    struct.pack_into("<I", ram, off + BM_PID, geo.pid)
    hp = BattleHP()
    team = [dataclasses.replace(t, stats=dict(t.stats)) for t in twins]
    hp.apply(bytes(ram), [[], team], (None, None))          # first poll: everything counts as old
    struct.pack_into("<iI", ram, off + BM_HP, 11, 37)       # the battle moves on
    team = [dataclasses.replace(t, stats=dict(t.stats)) for t in twins]
    hp.apply(bytes(ram), [[], team], (None, 1))
    assert [m.hp for m in team] == [37, 11, 37], [m.hp for m in team]

    # a twin KO'd, the next twin comes out: the new one must not show the fainted one's 0 HP.
    # RAM holds two battle copies with the twins' shared PID: a leftover copy (lower in memory)
    # that keeps the fainted twin's 0 HP, and the live slot, which the new twin overwrites.
    ram = bytearray(0x1000)
    leftover, live = 0x100, 0x400
    for o in (leftover, live):
        struct.pack_into("<H", ram, o + BM_SPECIES, geo.species_id)
        struct.pack_into("<I", ram, o + BM_PID, geo.pid)
    def poll(leftover_hp, live_hp, active):
        struct.pack_into("<iI", ram, leftover + BM_HP, leftover_hp, 37)
        struct.pack_into("<iI", ram, live + BM_HP, live_hp, 37)
        team = [dataclasses.replace(t, stats=dict(t.stats)) for t in twins]
        hp.apply(bytes(ram), [[], team], (None, active))
        return [m.hp for m in team]
    hp = BattleHP()
    poll(37, 37, 0)                                          # first poll
    assert poll(37, 20, 0) == [20, 37, 37]                   # twin 1 takes a hit
    assert poll(0, 0, 0) == [0, 37, 37]                      # twin 1 faints
    assert poll(0, 37, 1) == [0, 37, 37]                     # twin 2 comes out at full HP
    assert poll(0, 30, 1) == [0, 30, 37]                     # and takes a hit
    print("All battle tests passed.")


if __name__ == "__main__":
    test()
