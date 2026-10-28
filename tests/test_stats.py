"""Checks the stat formula, level scaling, and the edited copies the calculator uses
(nature, status, ability, held item, HP, speed). Run:  python tests/test_stats.py"""

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

    # changing the nature recalculates stats (HP is never affected)
    adamant = stats.adjusted(geo, nature="Adamant")
    assert adamant.nature == "Adamant" and geo.nature == "Relaxed"
    assert adamant.stats == stats.calc_stats(base, geo.ivs, geo.evs, 14, "Adamant")
    assert adamant.stats["HP"] == stats.calc_stats(base, geo.ivs, geo.evs, 14, "Relaxed")["HP"]
    assert stats.adjusted(geo, nature=geo.nature) is geo

    # status conditions
    assert stats.status_kind("Asleep (2)") == "Asleep" and stats.status_kind(None) == "OK"
    assert stats.status_kind("Toxic") == "Toxic" and stats.status_kind("???") == "OK"
    paralyzed = stats.with_status(geo, "Paralyzed")
    assert paralyzed.status == "Paralyzed" and geo.status == "Burned" and paralyzed.stats == geo.stats
    assert stats.with_status(geo, geo.status) is geo

    # abilities
    assert stats.with_ability(geo, "Sturdy").ability == "Sturdy" and geo.ability == "Rock Head"
    assert stats.with_ability(geo, geo.ability) is geo
    names = gamedata.all_ability_names()
    assert len(names) == 123 and "Torrent" in names and names == sorted(names)

    # held items: by name, with the game's ID kept in step; "" or None = nothing
    scarf = stats.with_item(geo, "Choice Scarf")
    assert scarf.held_item_name == "Choice Scarf" and scarf.held_item == gamedata.item_id("Choice Scarf") > 0
    assert stats.with_item(scarf, "").held_item_name is None and stats.with_item(scarf, None).held_item == 0
    assert stats.with_item(geo, geo.held_item_name) is geo                # no change -> same object
    assert scarf.stats == geo.stats and geo.held_item_name != "Choice Scarf"
    items = gamedata.all_item_names()
    assert "Leftovers" in items and items == sorted(items) and gamedata.item_id("Not An Item") == 0

    # turn-order speed: stat stages, then items, then paralysis
    spe = geo.stats["Spe"]
    assert stats.speed(geo) == spe and stats.speed(geo, 1) == int(spe * 1.5)
    assert stats.speed(geo, -2) == int(spe / 2) and stats.speed(geo, 6) == spe * 4
    assert stats.speed(paralyzed) == spe // 4
    assert stats.speed(scarf) == int(spe * 1.5) and stats.speed(stats.with_item(geo, "Iron Ball")) == spe // 2
    assert stats.speed(stats.with_item(geo, "Quick Powder")) == spe                  # only works for Ditto
    assert stats.speed(stats.with_status(scarf, "Paralyzed"), 1) == int(int(spe * 1.5) * 1.5) // 4
    # weather abilities, Quick Feet and Tailwind
    swimmer = stats.with_ability(geo, "Swift Swim")
    assert stats.speed(swimmer, weather="Rain") == spe * 2 and stats.speed(swimmer, weather="Sun") == spe
    assert stats.speed(stats.with_ability(geo, "Chlorophyll"), weather="Sun") == spe * 2
    assert stats.speed(geo, tailwind=True) == spe * 2
    feet = stats.with_ability(paralyzed, "Quick Feet")
    assert stats.speed(feet) == spe * 3 // 2                             # and paralysis doesn't slow it

    # current HP: clamped, scaled when max HP changes, percentages never hide damage
    assert stats.with_hp(geo, 30).hp == 30 and stats.with_hp(geo, 999).hp == 40
    assert stats.with_hp(geo, 20) is geo and geo.hp == 20                 # no change -> same object
    assert stats.with_hp(geo50, 20, of_max=40).hp == round(20 * geo50.max_hp / 40)
    assert stats.with_hp(geo50, 1, of_max=40).hp >= 1 and stats.with_hp(geo50, 0, of_max=40).hp == 0
    assert stats.hp_percent(20, 40) == 50 and stats.hp_percent(1, 400) == 1 and stats.hp_percent(399, 400) == 99
    assert stats.hp_percent(0, 40) == 0 and stats.hp_percent(40, 40) == 100
    assert stats.hp_from_percent(50, 40) == 20 and stats.hp_from_percent(1, 40) == 1
    assert stats.hp_from_percent(0, 40) == 0 and stats.hp_from_percent(100, 40) == 40

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
