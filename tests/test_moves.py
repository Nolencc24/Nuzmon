"""Checks moves whose power isn't a fixed number (Night Shade, Flail, Low Kick...).
Run:  python tests/test_moves.py"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # project folder

from tracker.game import gamedata, stats
from tracker.game.moves import effect


def fx(name, user, target=None, user_stages=None, target_stages=None):
    return effect(gamedata.move_by_name(name), user, target, user_stages, target_stages)


def test():
    # previews: IVs 31, EVs 0, Hardy, full HP
    snorlax = stats.preview("Snorlax", 30)           # 460 kg, Normal
    gengar = stats.preview("Gengar", 40)              # Ghost/Poison
    pidgey = stats.preview("Pidgey", 10)              # 1.8 kg, Normal/Flying
    geodude = stats.preview("Geodude", 20)            # Rock/Ground
    half = lambda mon: stats.with_hp(mon, mon.max_hp // 2)

    # ordinary moves are untouched
    e = fx("Tackle", pidgey, snorlax)
    assert (e.power, e.type, e.fixed, e.hits, e.note) == (35, "Normal", None, (1, 1), "")
    assert fx("Thunderbolt", None).power == 95                    # no user: listed power

    # fixed damage: the user's level, a set amount, or a range
    assert fx("Night Shade", gengar, snorlax).fixed == 0          # Normal types are immune to Ghost
    assert fx("Night Shade", gengar, pidgey).fixed == 0           # Pidgey is part Normal too
    assert fx("Night Shade", gengar, geodude).fixed == 40
    assert fx("Seismic Toss", snorlax, pidgey).fixed == 30
    assert fx("Seismic Toss", snorlax, gengar).fixed == 0         # Ghosts are immune to Fighting
    assert fx("Dragon Rage", pidgey, snorlax).fixed == 40 and fx("Sonic Boom", pidgey, snorlax).fixed == 20
    assert fx("Psywave", gengar, snorlax).fixed == (20, 60)
    assert fx("Super Fang", pidgey, snorlax).fixed == snorlax.hp // 2
    assert fx("Super Fang", pidgey, gengar).fixed == 0            # Normal move vs Ghost
    low = stats.with_hp(pidgey, 5)
    assert fx("Endeavor", low, snorlax).fixed == snorlax.hp - 5
    assert fx("Endeavor", pidgey, low).fixed == 0                 # target already lower: nothing
    assert fx("Fissure", stats.preview("Golem", 40), snorlax).fixed == snorlax.hp
    assert fx("Fissure", geodude, snorlax).fixed == 0             # level 20 vs level 30: fails
    assert fx("Fissure", geodude, pidgey).fixed == 0              # Flying: immune to Ground
    assert fx("Horn Drill", pidgey, snorlax).fixed == 0           # target's level is higher: fails
    assert fx("Counter", snorlax, pidgey).fixed is None and "can't be predicted" in fx("Counter", snorlax).note

    # power from HP
    assert fx("Eruption", stats.preview("Typhlosion", 50), snorlax).power == 150
    wailord = half(stats.preview("Wailord", 50))
    assert fx("Water Spout", wailord, snorlax).power == 150 * wailord.hp // wailord.max_hp   # 74: rounds down
    assert fx("Flail", pidgey).power == 20 and fx("Flail", stats.with_hp(snorlax, 1)).power == 200
    assert fx("Flail", stats.with_hp(pidgey, 1)).power == 150     # 1/31 HP is still the 150 band in Gen 4
    assert fx("Reversal", half(pidgey)).power == 40
    hurt = half(snorlax)
    assert fx("Crush Grip", pidgey, snorlax).power == 121
    assert fx("Wring Out", pidgey, hurt).power == 1 + 120 * hurt.hp // hurt.max_hp
    assert fx("Brine", pidgey, snorlax).power == 65 and fx("Brine", pidgey, half(snorlax)).power == 130

    # power from Speed, weight, friendship, stat boosts, PP
    slow, fast = stats.preview("Bronzong", 50), stats.preview("Jolteon", 50)
    expected = min(150, 1 + 25 * stats.speed(fast) // stats.speed(slow))
    assert fx("Gyro Ball", slow, fast).power == expected
    assert fx("Gyro Ball", slow, fast, target_stages={"Spe": 2}).power == min(150, 1 + 25 * stats.speed(fast, 2) // stats.speed(slow))
    assert fx("Low Kick", geodude, snorlax).power == 120 and fx("Grass Knot", geodude, pidgey).power == 20
    assert fx("Return", pidgey).power == 1                       # previews have no friendship
    import dataclasses
    friend = dataclasses.replace(pidgey, friendship=255)
    assert fx("Return", friend).power == 102 and fx("Frustration", friend).power == 1
    assert fx("Frustration", pidgey).power == 102
    assert fx("Punishment", pidgey, snorlax, target_stages={"Atk": 2, "Spe": 1, "Def": -1}).power == 120
    trump = dataclasses.replace(pidgey, moves=[("Trump Card", 1)])
    assert fx("Trump Card", trump).power == 200 and fx("Trump Card", pidgey).power == 40

    # power and type from the held item, or the IVs
    assert fx("Fling", pidgey).power == 0 and "Fails" in fx("Fling", pidgey).note
    assert fx("Fling", stats.with_item(pidgey, "Iron Ball")).power == 130
    gift = fx("Natural Gift", stats.with_item(pidgey, "Oran Berry"))
    assert (gift.power, gift.type) == (60, "Poison")
    assert (fx("Hidden Power", pidgey).type, fx("Hidden Power", pidgey).power) == pidgey.hidden_power

    # power doubled by a condition
    assert fx("Facade", pidgey).power == 70 and fx("Facade", stats.with_status(pidgey, "Burned")).power == 140
    assert fx("Smelling Salts", pidgey, stats.with_status(snorlax, "Paralyzed")).power == 120
    assert fx("Wake-Up Slap", pidgey, stats.with_status(snorlax, "Asleep")).power == 120
    assert fx("Wake-Up Slap", pidgey, snorlax).power == 60
    assert fx("Payback", slow, fast).power == 100 and fx("Payback", fast, slow).power == 50

    # the field: weather, Tailwind, Trick Room
    from tracker.game.field import Field
    rain, sun = Field(weather="Rain"), Field(weather="Sun")
    assert (fx("Weather Ball", pidgey).power, fx("Weather Ball", pidgey).type) == (50, "Normal")
    ball = effect(gamedata.move_by_name("Weather Ball"), pidgey, snorlax, field=rain)
    assert (ball.power, ball.type) == (100, "Water")
    assert effect(gamedata.move_by_name("Weather Ball"), pidgey, snorlax, field=Field(weather="Hail")).type == "Ice"
    golduck = stats.with_ability(stats.preview("Golduck", 30), "Cloud Nine")   # no weather
    assert effect(gamedata.move_by_name("Weather Ball"), pidgey, golduck, field=rain).power == 50
    assert effect(gamedata.move_by_name("Solar Beam"), pidgey, snorlax, field=rain).power == 60
    assert effect(gamedata.move_by_name("Solar Beam"), pidgey, snorlax, field=sun).power == 120
    windy = Field()
    windy.you.tailwind = True                                       # the user's side doubles its Speed
    gyro = gamedata.move_by_name("Gyro Ball")
    assert effect(gyro, slow, fast, field=windy).power == min(150, 1 + 25 * stats.speed(fast) // (2 * stats.speed(slow)))
    tail_foe = effect(gyro, slow, fast, field=windy, user_side="foe")   # now it's the target's Tailwind
    assert tail_foe.power == min(150, 1 + 25 * (2 * stats.speed(fast)) // stats.speed(slow))
    payback = gamedata.move_by_name("Payback")
    assert effect(payback, slow, fast, field=Field(trick_room=True)).power == 50   # slow moves first in Trick Room

    # weather abilities: when two setters come out together, the slower one's weather stays
    from tracker.game.field import weather_after_switch_ins
    kyogre = stats.with_ability(pidgey, "Drizzle")
    groudon = stats.with_ability(geodude, "Drought")
    assert weather_after_switch_ins("None", [(kyogre, 90), (groudon, 50)]) == ("Sun", groudon)
    assert weather_after_switch_ins("None", [(kyogre, 50), (groudon, 90)]) == ("Rain", kyogre)
    assert weather_after_switch_ins("Hail", [(kyogre, 70)]) == ("Rain", kyogre)
    assert weather_after_switch_ins("Hail", [(pidgey, 70), (snorlax, 30)]) == ("Hail", None)   # no setter
    assert weather_after_switch_ins("Rain", []) == ("Rain", None)

    # multi-hit moves
    assert fx("Double Kick", pidgey).hits == (2, 2) and fx("Fury Attack", pidgey).hits == (2, 5)
    assert fx("Rock Blast", stats.with_ability(geodude, "Skill Link")).hits == (5, 5)
    assert fx("Triple Kick", pidgey).hits == (3, 3)

    # moves that need a target say so instead of guessing
    assert fx("Low Kick", geodude).note == "Depends on the target" and fx("Super Fang", pidgey).fixed is None

    # random moves: a typical value and a note
    assert fx("Magnitude", geodude, snorlax).power == 70 and "Random" in fx("Magnitude", geodude).note
    print("All moves tests passed.")


if __name__ == "__main__":
    test()
