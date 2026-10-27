"""Checks one side of the damage calculator (CalcSide): hand edits, pinning, starting over,
and values that follow the live battle. Run:  python tests/test_calc.py

Builds the real Qt widgets without showing a window (Qt's "offscreen" platform).
"""

import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # project folder
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")    # no window needed

from PySide6.QtWidgets import QApplication

from tracker.game.decoder import encrypt, parse
from tracker.game.samples import GEODUDE, SHINY_CUBONE, as_party
from tracker.ui.pages.damage_calc import CalcSide, Edits

NO_STAGES = {"Atk": 0, "Def": 0, "Spe": 0, "SpA": 0, "SpD": 0, "Acc": 0, "Eva": 0}


def battler(mon, item=None, **stages):
    """A stand-in for game.battle.Battler with just what CalcSide reads."""
    return SimpleNamespace(pid=mon.pid, item=item, stages={**NO_STAGES, **stages})


def edit_everything(side: CalcSide):
    side.set_level(30)
    side.set_stat("iv", "Atk", 0)
    side.set_stat("ev", "Spe", 100)
    side.set_hp(5)
    side.set_nature("Adamant")
    side.set_status("Toxic")
    side.set_ability("Sturdy")
    side.set_item("Leftovers")
    side.set_stage("Atk", 2)


def test():
    app = QApplication.instance() or QApplication([])
    geo = parse(encrypt(as_party(GEODUDE, 14, 22, 37)))
    cub = parse(encrypt(as_party(SHINY_CUBONE, 9, 6, 28)))
    team = [geo, cub, None, None, None, None]

    side = CalcSide("You")
    side.set_live(geo, team)
    assert side.subject() is geo and not side.pinned and side.edits == Edits()

    # every kind of hand edit shows up in subject() and pins the side
    edit_everything(side)
    s = side.subject()
    assert side.pinned and s.level == 30 and s.ivs["Atk"] == 0 and s.evs["Spe"] == 100
    assert s.hp == 5 and s.nature == "Adamant" and s.status == "Toxic"
    assert s.ability == "Sturdy" and s.held_item_name == "Leftovers" and side.stages()["Atk"] == 2
    assert geo.level == 14 and geo.nature == "Relaxed"                    # the game's copy is untouched
    assert side.level.text() == "30" and side.item.value() == "Leftovers"   # the boxes show it too

    # every way of starting over drops every edit
    side.reset()
    assert side.edits == Edits() and not side.pinned and side.subject() is geo

    edit_everything(side)
    side.select(cub)                                   # clicking a bench row
    assert side.edits == Edits() and side.pinned and side.subject() is cub and side.slot() == 1

    edit_everything(side)
    side.species.set_value("Pikachu")                  # picking another species: a preview...
    s = side.subject()
    assert side.edits == Edits(level=30) and s.preview and s.species == "Pikachu" and s.level == 30
    side.species.set_value("Cubone")                   # ...or one of your own Pokémon
    assert side.edits == Edits() and side.subject() is cub
    side.reset()

    # values the game already has don't count as edits
    side.set_level(geo.level)
    side.set_nature(geo.nature)
    assert side.edits == Edits() and not side.pinned

    # in battle, stat stages and the held item follow the Pokémon that's out
    side.set_live(geo, team, battler(geo, item="Oran Berry", Atk=2, Spe=-1), active=0)
    assert side.stages() == {"Atk": 2, "Def": 0, "SpA": 0, "SpD": 0, "Spe": -1}
    assert side.subject().held_item_name == "Oran Berry"
    side.set_live(geo, team, battler(geo, item=None, Atk=2, Spe=-1), active=0)        # berry eaten
    assert side.subject().held_item_name is None

    # a stage picked by hand wins over the battle's; the others keep following it
    side.set_stage("Def", -3)
    side.set_live(geo, team, battler(geo, Atk=4), active=0)
    assert side.stages()["Def"] == -3 and side.stages()["Atk"] == 4
    side.reset()

    # a bench Pokémon or a preview isn't the one out: no live stages
    side.select(cub)
    assert side.stages()["Atk"] == 0
    side.species.set_value("Pikachu")
    assert side.stages()["Atk"] == 0
    side.reset()

    # twins (same PID): only the one that's out gets the battle's stages
    twins = [geo, parse(encrypt(as_party(GEODUDE, 14, 37, 37))), None, None, None, None]
    assert twins[0].pid == twins[1].pid
    side.set_live(twins[1], twins, battler(geo, Atk=1), active=1)
    assert side.slot() == 1 and side.stages()["Atk"] == 1
    side.select(twins[0])
    assert side.slot() == 0 and side.stages()["Atk"] == 0

    del app
    print("All calc tests passed.")


if __name__ == "__main__":
    test()
