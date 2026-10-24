"""Checks the stat formula and level scaling. Run:  python tests/test_stats.py"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # project folder

from tracker.game import gamedata, stats
from tracker.game.decoder import encrypt, parse
from tracker.game.samples import GEODUDE, as_party


def test():
    # Bulbapedia's worked example: Adamant Garchomp, level 78
    garchomp = gamedata.species_by_name("Garchomp")["base_stats"]
    ivs = {"HP": 24, "Atk": 12, "Def": 30, "SpA": 16, "SpD": 23, "Spe": 5}
    evs = {"HP": 74, "Atk": 190, "Def": 91, "SpA": 48, "SpD": 84, "Spe": 23}
    got = stats.calc_stats(garchomp, ivs, evs, 78, "Adamant")
    assert got == {"HP": 289, "Atk": 278, "Def": 193, "Spe": 171, "SpA": 135, "SpD": 171}, got

    # Shedinja always has 1 HP
    assert stats.calc_stats(gamedata.species_by_name("Shedinja")["base_stats"],
                            ivs, evs, 50, "Hardy", 292)["HP"] == 1

    # level scaling of a real Pokémon keeps its IVs/EVs/nature and HP percentage
    geo = parse(encrypt(as_party(GEODUDE, 14, 20, 40)))
    geo50 = stats.with_level(geo, 50)
    assert geo50.level == 50 and geo50.ivs == geo.ivs and geo50.nature == geo.nature
    base = gamedata.species(74)["base_stats"]
    assert geo50.stats == stats.calc_stats(base, geo.ivs, geo.evs, 50, geo.nature)
    assert geo50.hp == round(20 * geo50.max_hp / 40)
    assert geo.level == 14 and stats.with_level(geo, 14) is geo           # original untouched

    # changing IVs/EVs recalculates stats and Hidden Power; values are clamped
    tweaked = stats.adjusted(geo, ivs={"Atk": 0, "Spe": 99}, evs={"Atk": 252, "HP": 300})
    assert tweaked.ivs["Atk"] == 0 and tweaked.ivs["Spe"] == 31 and tweaked.evs["HP"] == 252
    assert tweaked.ivs["Def"] == geo.ivs["Def"] and tweaked.level == geo.level
    assert tweaked.stats == stats.calc_stats(base, tweaked.ivs, tweaked.evs, 14, geo.nature)
    from tracker.game.decoder import hidden_power_of
    assert tweaked.hidden_power == hidden_power_of(tweaked.ivs)
    assert stats.adjusted(geo, ivs=dict(geo.ivs)) is geo                  # no change -> same object

    # previews: defaults, forms, moves
    p = stats.preview("Rotom-Wash", 30, [("Thunderbolt", 15), ("", 0)])
    assert p.preview and p.species_id == 479 and p.form == 2 and p.level == 30
    assert p.ivs["Atk"] == 31 and p.evs["Atk"] == 0 and p.nature == "Hardy" and p.hp == p.max_hp
    assert p.moves == [("Thunderbolt", 15)] and p.move_ids == [85]
    assert stats.form_name(p) == "Rotom-Wash"
    assert stats.preview("Not A Pokemon", 5) is None
    assert len(gamedata.all_species_names()) >= 493
    print("All stats tests passed.")


if __name__ == "__main__":
    test()
