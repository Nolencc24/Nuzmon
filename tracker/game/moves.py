"""
Moves whose power isn't a fixed number (Gen 4 rules).

Most moves just use the power in tracker/data/moves.json. These don't:

  * fixed damage: Night Shade / Seismic Toss (the user's level), Dragon Rage (40),
    Sonic Boom (20), Psywave (50-150% of the user's level), Super Fang (half the target's
    HP), Endeavor (down to the user's HP), and the one-hit KOs (Fissure, Guillotine,
    Horn Drill, Sheer Cold). These skip the damage formula entirely.
  * power that depends on the situation: Eruption, Water Spout, Flail, Reversal, Wring Out,
    Crush Grip (HP), Gyro Ball (Speed), Low Kick, Grass Knot (weight), Return, Frustration
    (friendship), Punishment (stat boosts), Trump Card (PP left), Fling, Natural Gift (held
    item), Facade, Smelling Salts, Wake-Up Slap, Brine, Payback, and Hidden Power.
  * random or turn-by-turn power the tracker can't know (Magnitude, Present, Rollout...):
    a typical value plus a note.

    from tracker.game import moves
    e = moves.effect(gamedata.move_by_name("Night Shade"), user, target)
    e.fixed   # 14 for a level 14 user: always 14 HP of damage
"""

from __future__ import annotations

from dataclasses import dataclass

from . import gamedata
from .decoder import Pokemon
from .stats import speed, status_kind


@dataclass
class MoveEffect:
    """What a move does in this situation. The damage formula uses power and type, unless
    fixed is set: then the move does exactly that much damage (a number, or a (low, high)
    range for Psywave) and the formula is skipped."""
    power: int
    type: str
    fixed: int | tuple | None = None
    hits: tuple = (1, 1)          # (fewest, most) hits
    note: str = ""                # why the power is what it is (shown as a tooltip)


OHKO = {"Fissure", "Guillotine", "Horn Drill", "Sheer Cold"}
COUNTERS = {"Counter": "physical", "Mirror Coat": "special", "Metal Burst": "any"}


def _hp_fraction(mon: Pokemon) -> tuple[int, int]:
    return mon.hp or 0, mon.max_hp or 1


def _weight_power(kg: float) -> int:
    """Low Kick / Grass Knot: heavier targets take more."""
    for limit, power in ((10, 20), (25, 40), (50, 60), (100, 80), (200, 100)):
        if kg < limit:
            return power
    return 120


def _flail_power(mon: Pokemon) -> int:
    """Flail / Reversal: Gen 4 checks 64 x HP / max HP against this table."""
    hp, mx = _hp_fraction(mon)
    n = 64 * hp // mx
    for limit, power in ((1, 200), (5, 150), (12, 100), (21, 80), (42, 40)):
        if n <= limit:
            return power
    return 20


def _trump_card_power(pp_left_after: int) -> int:
    return {0: 200, 1: 80, 2: 60, 3: 50}.get(pp_left_after, 40)


def _immune(mtype: str, target: Pokemon | None) -> bool:
    """True if target can't be hit by this type at all (e.g. Night Shade vs a Normal type).
    Fixed-damage moves ignore type matchups except for these immunities."""
    if target is None:
        return False
    if mtype == "Ground" and target.ability == "Levitate":
        return True
    sp = gamedata.species(target.species_id, target.form)
    return sp is not None and gamedata.effectiveness(mtype, sp["types"]) == 0


def _hits(move: dict, user: Pokemon | None) -> tuple[int, int]:
    multi = move["multihit"]
    if multi is None:
        return 1, 1
    if isinstance(multi, int):
        return multi, multi
    if user is not None and user.ability == "Skill Link":
        return multi[1], multi[1]
    return tuple(multi)


def effect(move: dict, user: Pokemon | None, target: Pokemon | None = None,
           user_stages: dict | None = None, target_stages: dict | None = None) -> MoveEffect:
    """How move works when user uses it on target. Stages are each side's stat stages
    (e.g. {"Spe": -1}), used for Gyro Ball, Payback and Punishment. With no user, or no
    target for a move that needs one, the move's listed power is returned with a note."""
    name, power, mtype = move["name"], move["power"] or 0, move["type"]
    hits = _hits(move, user)
    out = lambda power=power, mtype=mtype, fixed=None, note="": MoveEffect(power, mtype, fixed, hits, note)
    if hits != (1, 1):
        lo, hi = hits
        hit_note = f"Hits {lo} times" if lo == hi else f"Hits {lo}-{hi} times (2 or 3 hits 75% of the time)"
        if name == "Triple Kick":
            hit_note = "Hits up to 3 times, with 10, then 20, then 30 power"
        return out(note=hit_note)
    if user is None:
        return out()
    us, ts = user_stages or {}, target_stages or {}

    # ---- fixed damage
    if _immune(mtype, target) and (move["fixed_damage"] or name in {"Psywave", "Super Fang", "Endeavor"} | OHKO):
        return out(0, fixed=0, note=f"No effect: {target.species} can't be hit by {mtype} moves")
    fd = move["fixed_damage"]
    if fd == "level":
        return out(0, fixed=user.level, note=f"Always does damage equal to the user's level ({user.level})")
    if isinstance(fd, int):
        return out(0, fixed=fd, note=f"Always does {fd} damage")
    if name == "Psywave":
        lo, hi = max(1, user.level // 2), max(1, user.level * 3 // 2)
        return out(0, fixed=(lo, hi), note=f"Random damage from 50% to 150% of the user's level ({lo}-{hi})")
    if name in COUNTERS or name == "Bide":
        kind = {"physical": "physical damage", "special": "special damage", "any": "damage"}.get(COUNTERS.get(name), "damage")
        mult = "1.5x" if name == "Metal Burst" else "2x"
        return out(0, note=f"Hits back {mult} the {kind} the user took (can't be predicted)")

    needs_target = name in {"Super Fang", "Endeavor", "Wring Out", "Crush Grip", "Gyro Ball", "Low Kick",
                            "Grass Knot", "Punishment", "Smelling Salts", "Wake-Up Slap", "Brine",
                            "Payback"} | OHKO
    if needs_target and target is None:
        return out(note="Depends on the target")

    if name == "Super Fang":
        hp = max(1, (target.hp or 0) // 2)
        return out(0, fixed=hp, note=f"Halves the target's current HP ({hp} damage)")
    if name == "Endeavor":
        dmg = max(0, (target.hp or 0) - (user.hp or 0))
        return out(0, fixed=dmg, note=f"Cuts the target's HP down to the user's ({dmg} damage)")
    if name in OHKO:
        if (target.level or 0) > (user.level or 0):
            return out(0, fixed=0, note="Fails: the target is a higher level than the user")
        return out(0, fixed=target.hp or 0, note="One-hit KO if it hits (accuracy goes up with the level gap)")

    # ---- power from HP
    if name in ("Eruption", "Water Spout"):
        hp, mx = _hp_fraction(user)
        p = max(1, 150 * hp // mx)
        return out(p, note=f"150 x the user's HP fraction ({hp}/{mx})")
    if name in ("Flail", "Reversal"):
        return out(_flail_power(user), note="Stronger the lower the user's HP (20 at full, 200 at a sliver)")
    if name in ("Wring Out", "Crush Grip"):
        hp, mx = _hp_fraction(target)
        return out(1 + 120 * hp // mx, note=f"Stronger the more HP the target has ({hp}/{mx})")
    if name == "Brine":
        hp, mx = _hp_fraction(target)
        return out(130 if 2 * hp <= mx else 65, note="Doubles to 130 when the target is at half HP or less")

    # ---- power from stats, weight, friendship, PP
    if name == "Gyro Ball":
        mine, theirs = speed(user, us.get("Spe", 0)), speed(target, ts.get("Spe", 0))
        p = min(150, 1 + 25 * theirs // max(1, mine))
        return out(p, note=f"Stronger the slower the user is than the target (Speed {mine} vs {theirs})")
    if name in ("Low Kick", "Grass Knot"):
        sp = gamedata.species(target.species_id, target.form)
        kg = sp["weight_kg"] if sp else 0
        return out(_weight_power(kg), note=f"Stronger against heavier targets ({target.species}: {kg} kg)")
    if name in ("Return", "Frustration"):
        f = user.friendship or 0
        p = max(1, (f if name == "Return" else 255 - f) * 2 // 5)
        return out(p, note=f"Depends on friendship ({f}/255)")
    if name == "Punishment":
        boosts = sum(v for v in ts.values() if v > 0)
        return out(min(200, 60 + 20 * boosts), note=f"60 + 20 for each stat boost the target has (+{boosts})")
    if name == "Trump Card":
        pp = next((pp for n, pp in user.moves if n == name), move["pp"])
        return out(_trump_card_power(max(0, pp - 1)), note=f"Stronger with less PP left ({pp} PP before using it)")

    # ---- power from the held item
    if name == "Fling":
        item = gamedata.item_by_name(user.held_item_name)
        if not item or not item["fling_power"]:
            return out(0, note="Fails: the user isn't holding an item that can be flung")
        return out(item["fling_power"], note=f"Throws the held item ({item['name']})")
    if name == "Natural Gift":
        item = gamedata.item_by_name(user.held_item_name)
        gift = item["natural_gift"] if item else None
        if not gift:
            return out(0, note="Fails: the user isn't holding a berry")
        return out(gift["basePower"], gift["type"], note=f"Type and power come from the berry ({item['name']})")
    if name == "Hidden Power" and user.hidden_power:
        hp_type, hp_power = user.hidden_power
        return out(hp_power, hp_type, note="Type and power come from the user's IVs")

    # ---- power doubled by a condition
    if name == "Facade":
        hurt = status_kind(user.status) in ("Burned", "Poisoned", "Toxic", "Paralyzed")
        return out(140 if hurt else 70, note="Doubles to 140 when the user is burned, poisoned or paralyzed")
    if name == "Smelling Salts":
        para = status_kind(target.status) == "Paralyzed"
        return out(120 if para else 60, note="Doubles to 120 against a paralyzed target (and cures it)")
    if name == "Wake-Up Slap":
        asleep = status_kind(target.status) == "Asleep"
        return out(120 if asleep else 60, note="Doubles to 120 against a sleeping target (and wakes it)")
    if name == "Payback":
        later = speed(user, us.get("Spe", 0)) < speed(target, ts.get("Spe", 0))
        return out(100 if later else 50, note="Doubles to 100 when the user moves after the target")

    # ---- can't be known ahead of time: a typical value and a note
    notes = {
        "Magnitude": (70, "Random: Magnitude 4-10 = 10-150 power (70 is the most common)"),
        "Present": (80, "Random: 40, 80 or 120 power, or heals the target instead"),
        "Spit Up": (100, "100 power per Stockpile (1-3)"),
        "Weather Ball": (50, "Doubles to 100 and changes type in weather (weather isn't tracked yet)"),
        "Avalanche": (60, "Doubles to 120 if the target hit the user first this turn"),
        "Revenge": (60, "Doubles to 120 if the target hit the user first this turn"),
        "Assurance": (50, "Doubles to 100 if the target was already hurt this turn"),
        "Pursuit": (40, "Doubles to 80 if the target is switching out"),
        "Rollout": (30, "Doubles every turn it keeps going (and after Defense Curl)"),
        "Ice Ball": (30, "Doubles every turn it keeps going (and after Defense Curl)"),
        "Fury Cutter": (10, "Doubles with each hit in a row, up to 160"),
        "Rage": (20, "Raises the user's Attack each time it's hit while raging"),
        "Beat Up": (10, "One hit per healthy party member, each using that member's Attack"),
    }
    if name in notes:
        p, note = notes[name]
        return out(p, note=note)
    return out()
