"""Checks the Gen 4 damage formula and the hits-to-KO chances. Run:  python tests/test_damage.py"""

import dataclasses
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # project folder

from tracker.game import gamedata, stats
from tracker.game.damage import calculate, end_of_turn, hit_rolls
from tracker.game.field import Field


def settings(name, crit=False, power=None, mtype=None, category=None, fixed=None, hits=(1, 1)):
    """What a move row would hand over (see MoveRow.settings)."""
    m = gamedata.move_by_name(name)
    return {"move": m, "power": m["power"] if power is None else power, "type": mtype or m["type"],
            "category": category or m["category"], "crit": crit, "fixed": fixed, "hits": hits, "note": ""}


def with_stats(mon, **changes):
    return dataclasses.replace(mon, stats={**mon.stats, **changes})


def test():
    # Bulbapedia's worked example: level 75 Glaceon (Atk 123) uses Ice Fang on Garchomp (Def 163):
    # STAB, 4x effective -> 168 to 196
    glaceon = with_stats(stats.preview("Glaceon", 75), Atk=123)
    garchomp = with_stats(stats.preview("Garchomp", 65), Def=163)
    ice_fang = settings("Ice Fang")
    rolls = hit_rolls(glaceon, garchomp, ice_fang, ["Ice"], ["Dragon", "Ground"])
    assert (rolls[0], rolls[-1], len(rolls)) == (168, 196, 16), rolls
    r = calculate(glaceon, garchomp, ice_fang, ["Ice"], ["Dragon", "Ground"])
    assert (r.low, r.high) == (168, 196)

    # burn halves physical damage (not with Guts); Reflect halves it too, but not crits
    burned = stats.with_status(glaceon, "Burned")
    assert hit_rolls(burned, garchomp, ice_fang, ["Ice"], ["Dragon", "Ground"])[-1] < 196 // 2 + 10
    guts = stats.with_ability(burned, "Guts")
    assert hit_rolls(guts, garchomp, ice_fang, ["Ice"], ["Dragon", "Ground"])[-1] > 196
    walled = Field()
    walled.foe.reflect = True
    screened = hit_rolls(glaceon, garchomp, ice_fang, ["Ice"], ["Dragon", "Ground"], field=walled)
    assert screened[-1] < 110
    crit = settings("Ice Fang", crit=True)
    assert hit_rolls(glaceon, garchomp, crit, ["Ice"], ["Dragon", "Ground"], field=walled)[-1] > 350

    # a crit ignores the attacker's drops and the defender's boosts
    plain = hit_rolls(glaceon, garchomp, crit, ["Ice"], ["Dragon", "Ground"])
    assert hit_rolls(glaceon, garchomp, crit, ["Ice"], ["Dragon", "Ground"], {"Atk": -2}, {"Def": 2}) == plain
    assert hit_rolls(glaceon, garchomp, ice_fang, ["Ice"], ["Dragon", "Ground"], {"Atk": 2})[-1] > 196

    # no STAB without the type; effectiveness and immunities
    tackle = settings("Tackle")
    pidgey, gengar = stats.preview("Pidgey", 20), stats.preview("Gengar", 40)
    assert calculate(pidgey, gengar, tackle, ["Normal", "Flying"], ["Ghost", "Poison"]).no_effect
    quake = settings("Earthquake")
    levitator = stats.preview("Bronzong", 40)                    # Levitate
    assert "Levitate" in calculate(garchomp, levitator, quake, ["Dragon", "Ground"], ["Steel", "Psychic"]).no_effect
    breaker = stats.with_ability(garchomp, "Mold Breaker")
    assert calculate(breaker, levitator, quake, ["Dragon", "Ground"], ["Steel", "Psychic"]).high > 0
    shedinja = stats.preview("Shedinja", 30)
    water_gun = settings("Water Gun")                            # neutral on Bug/Ghost: blocked
    assert calculate(pidgey, shedinja, water_gun, [], ["Bug", "Ghost"]).no_effect == "no effect (Wonder Guard)"
    assert calculate(pidgey, shedinja, settings("Ember"), [], ["Bug", "Ghost"]).high >= 1   # super effective
    assert calculate(pidgey, gengar, settings("Growl"), [], []) is None          # status move

    # hits to KO: the fewest hits with at least a 50% chance
    target = stats.preview("Snorlax", 50)
    per_hit = hit_rolls(glaceon, target, ice_fang, ["Ice"], ["Normal"])
    assert per_hit == [78, 79, 79, 81, 82, 82, 84, 85, 85, 87, 87, 88, 90, 90, 91, 93]
    r = calculate(glaceon, stats.with_hp(target, 85), ice_fang, ["Ice"], ["Normal"])   # 9 of 16 rolls KO
    assert (r.ko_hits, r.ko_text()) == (1, "56% to OHKO")
    r = calculate(glaceon, stats.with_hp(target, 86), ice_fang, ["Ice"], ["Normal"])   # 7 of 16: under 50%
    assert r.chances[0] == 7 / 16 and r.ko_hits == 2 and r.ko_text() == "guaranteed 2HKO"
    just_above = stats.with_hp(target, per_hit[-1] + 1)          # can't OHKO; two hits always do it
    r = calculate(glaceon, just_above, ice_fang, ["Ice"], ["Normal"])
    assert r.ko_hits == 2 and r.ko_text() == "guaranteed 2HKO" and r.chances[0] == 0
    lucky = stats.with_hp(target, per_hit[13])                  # 3 of 16 rolls OHKO (19%): show the 2HKO
    r = calculate(glaceon, lucky, ice_fang, ["Ice"], ["Normal"])
    assert r.chances[0] < 0.5 and r.ko_hits == 2

    # end-of-turn damage and healing between hits
    mon = stats.preview("Snorlax", 50)
    assert end_of_turn(stats.with_item(mon, "Leftovers"), ["Normal"], "None", 1)[0] == mon.max_hp // 16
    assert end_of_turn(stats.with_status(mon, "Burned"), ["Normal"], "None", 1)[0] == -(mon.max_hp // 8)
    toxic = stats.with_status(mon, "Toxic")
    assert end_of_turn(toxic, ["Normal"], "None", 3)[0] == -(mon.max_hp * 3 // 16)
    assert end_of_turn(mon, ["Normal"], "Sandstorm", 1)[0] == -(mon.max_hp // 16)
    assert end_of_turn(mon, ["Rock"], "Sandstorm", 1)[0] == 0
    guard = stats.with_ability(stats.with_status(mon, "Poisoned"), "Magic Guard")
    assert end_of_turn(guard, ["Normal"], "Sandstorm", 1)[0] == 0
    # Leftovers can turn a 2HKO into a 3HKO
    hp = per_hit[0] + per_hit[0] - 1 + 10
    left = stats.with_hp(stats.with_item(target, "Leftovers"), min(hp, target.max_hp))
    bare = stats.with_hp(target, min(hp, target.max_hp))
    with_left = calculate(glaceon, left, ice_fang, ["Ice"], ["Normal"])
    without = calculate(glaceon, bare, ice_fang, ["Ice"], ["Normal"])
    assert with_left.chances[1] <= without.chances[1] and "Leftovers +1/16" in with_left.notes

    # Focus Sash: survives one hit from full HP
    sashed = stats.with_item(stats.preview("Pidgey", 10), "Focus Sash")
    r = calculate(glaceon, sashed, ice_fang, ["Ice"], ["Normal", "Flying"])
    assert r.low >= sashed.max_hp and r.ko_hits == 2

    # multi-hit: 2-5 hits add up; fixed damage
    rock_blast = settings("Rock Blast", hits=(2, 5))
    one = hit_rolls(garchomp, target, rock_blast, ["Dragon", "Ground"], ["Normal"])
    r = calculate(garchomp, target, rock_blast, ["Dragon", "Ground"], ["Normal"])
    assert (r.low, r.high) == (2 * one[0], 5 * one[-1])
    shade = settings("Night Shade", fixed=40)
    r = calculate(gengar, target, shade, ["Ghost"], ["Normal"])
    assert (r.low, r.high) == (40, 40) and r.ko_hits == -(-target.hp // 40)
    assert calculate(gengar, target, settings("Night Shade", fixed=0), [], []).no_effect
    fang = calculate(pidgey, target, settings("Super Fang", fixed=target.hp // 2), [], ["Normal"])
    assert fang.low == target.hp // 2 and fang.chances[0] == 0
    print("All damage tests passed.")


if __name__ == "__main__":
    test()
