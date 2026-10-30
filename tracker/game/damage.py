"""
The Gen 4 (DPPt / HGSS) damage formula, and how many hits it takes to KO.

    from tracker.game import damage
    result = damage.calculate(attacker, defender, settings, attacker_types, defender_types)
    result.low, result.high          # damage range of one use of the move
    result.ko_hits, result.ko_chance # fewest uses with at least a 50% chance to KO, and that chance

settings is one of CalcSide.moves() (power, type, category, crit, fixed damage, hits; see
game/moves.py). The order of operations and the rounding follow the games:

    base = floor(floor(floor(2 x Level / 5 + 2) x Power x Atk / Def) / 50)
    x burn (0.5) x screens (0.5) x weather (1.5 / 0.5), + 2, x crit (2), x Life Orb (1.3),
    x random (85-100%, 16 rolls), x STAB (1.5), x each type's effectiveness,
    x Filter / Solid Rock / Expert Belt / Tinted Lens / resist berry

with Atk, Def and Power first changed by stat stages (a crit ignores the attacker's drops
and the defender's boosts), abilities and items. Hits to KO start from the defender's
current HP, and count end-of-turn damage and healing between hits (poison, burn,
sandstorm, hail, Leftovers...). Random crits aren't counted; turn on Crit for those.

Not covered: doubles (spread moves), Helping Hand, Charge, Flash Fire's boost, Mud Sport /
Water Sport, and moves that change mid-fight (Rollout, Fury Cutter...).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from . import gamedata
from .decoder import Pokemon
from .field import Field, current_weather
from .stats import stage_multiplier, status_kind

TYPE_ITEMS = {   # held items that power up one type by 20%
    "Silk Scarf": "Normal", "Black Belt": "Fighting", "Sharp Beak": "Flying", "Poison Barb": "Poison",
    "Soft Sand": "Ground", "Hard Stone": "Rock", "Silver Powder": "Bug", "Spell Tag": "Ghost",
    "Metal Coat": "Steel", "Charcoal": "Fire", "Mystic Water": "Water", "Miracle Seed": "Grass",
    "Magnet": "Electric", "Twisted Spoon": "Psychic", "Never-Melt Ice": "Ice", "Dragon Fang": "Dragon",
    "Black Glasses": "Dark", "Sea Incense": "Water", "Wave Incense": "Water", "Odd Incense": "Psychic",
    "Rock Incense": "Rock", "Rose Incense": "Grass", "Flame Plate": "Fire", "Splash Plate": "Water",
    "Zap Plate": "Electric", "Meadow Plate": "Grass", "Icicle Plate": "Ice", "Fist Plate": "Fighting",
    "Toxic Plate": "Poison", "Earth Plate": "Ground", "Sky Plate": "Flying", "Mind Plate": "Psychic",
    "Insect Plate": "Bug", "Stone Plate": "Rock", "Spooky Plate": "Ghost", "Draco Plate": "Dragon",
    "Dread Plate": "Dark", "Iron Plate": "Steel",
}
ORBS = {"Adamant Orb": (483, {"Dragon", "Steel"}), "Lustrous Orb": (484, {"Water", "Dragon"}),
        "Griseous Orb": (487, {"Ghost", "Dragon"})}   # x1.2 for Dialga / Palkia / Giratina
RESIST_BERRIES = {   # halve one super-effective hit of their type (Chilan: any Normal hit)
    "Occa Berry": "Fire", "Passho Berry": "Water", "Wacan Berry": "Electric", "Rindo Berry": "Grass",
    "Yache Berry": "Ice", "Chople Berry": "Fighting", "Kebia Berry": "Poison", "Shuca Berry": "Ground",
    "Coba Berry": "Flying", "Payapa Berry": "Psychic", "Tanga Berry": "Bug", "Charti Berry": "Rock",
    "Kasib Berry": "Ghost", "Haban Berry": "Dragon", "Colbur Berry": "Dark", "Babiri Berry": "Steel",
    "Chilan Berry": "Normal",
}
PINCH = {"Overgrow": "Grass", "Blaze": "Fire", "Torrent": "Water", "Swarm": "Bug"}
ABSORB = {"Volt Absorb": "Electric", "Motor Drive": "Electric", "Water Absorb": "Water",
          "Dry Skin": "Water", "Flash Fire": "Fire", "Levitate": "Ground"}
OHKO = {"Fissure", "Guillotine", "Horn Drill", "Sheer Cold"}
MAX_HITS = 10            # how far the hits-to-KO count goes


@dataclass
class Result:
    """Damage of one use of a move, and how many uses it takes to KO."""
    low: int
    high: int
    max_hp: int
    ko_hits: int | None = None    # fewest uses with >= 50% chance to KO (None: not within MAX_HITS)
    ko_chance: float = 0.0        # the chance to KO within ko_hits uses
    chances: list = field(default_factory=list)   # chance to KO within 1, 2, 3... uses
    no_effect: str = ""           # why the move does nothing ("" if it does damage)
    notes: list = field(default_factory=list)     # what else was counted (end-of-turn damage...)

    def percent(self) -> tuple[float, float]:
        return 100 * self.low / self.max_hp, 100 * self.high / self.max_hp

    def ko_text(self) -> str:
        """"OHKO", "53% to 2HKO", "guaranteed 3HKO", or why there's no KO."""
        if self.no_effect:
            return self.no_effect
        if self.ko_hits is None:
            return f"no KO in {MAX_HITS} hits"
        name = "OHKO" if self.ko_hits == 1 else f"{self.ko_hits}HKO"
        if self.ko_chance >= 0.9995:
            return f"guaranteed {name}"
        return f"{int(self.ko_chance * 100)}% to {name}"


# ---------------------------------------------------------------- the formula

def _effectiveness(mtype: str, defender_types: list, scrappy: bool) -> list[float]:
    """Multiplier against each of the defender's types (applied one at a time)."""
    out = []
    for t in defender_types:
        e = gamedata.effectiveness(mtype, [t])
        if scrappy and t == "Ghost" and mtype in ("Normal", "Fighting"):
            e = 1.0
        out.append(e)
    return out


def _no_effect(move: dict, mtype: str, total: float, defender: Pokemon, mold_breaker: bool) -> str:
    """Why the move can't hurt the defender, or ""."""
    if total == 0:
        return "no effect (type immunity)"
    if mold_breaker:
        return ""
    ability = defender.ability
    if ABSORB.get(ability) == mtype:
        return f"no effect ({ability})"
    if ability == "Wonder Guard" and total <= 1:
        return "no effect (Wonder Guard)"
    if ability == "Soundproof" and "sound" in move["flags"]:
        return "no effect (Soundproof)"
    return ""


def _attack(att: Pokemon, defender: Pokemon, physical: bool, stage: int, crit: bool, mtype: str,
            weather: str, mold_breaker: bool) -> int:
    if crit:
        stage = max(stage, 0)            # a crit ignores the attacker's stat drops
    a = int(att.stats["Atk" if physical else "SpA"] * stage_multiplier(stage))
    ability, item, num = att.ability, att.held_item_name, att.species_id
    if physical:
        if ability in ("Huge Power", "Pure Power"):
            a *= 2
        if ability == "Hustle" or (ability == "Guts" and status_kind(att.status) != "OK"):
            a = a * 3 // 2
        if ability == "Flower Gift" and weather == "Sun":
            a = a * 3 // 2
        if item == "Choice Band":
            a = a * 3 // 2
        if item == "Thick Club" and num in (104, 105):          # Cubone, Marowak
            a *= 2
    else:
        if ability == "Solar Power" and weather == "Sun":
            a = a * 3 // 2
        if item == "Choice Specs":
            a = a * 3 // 2
        if item == "Soul Dew" and num in (380, 381):            # Latias, Latios
            a = a * 3 // 2
        if item == "Deep Sea Tooth" and num == 366:             # Clamperl
            a *= 2
    if item == "Light Ball" and num == 25:                      # Pikachu (both stats in Gen 4)
        a *= 2
    if not mold_breaker and defender.ability == "Thick Fat" and mtype in ("Fire", "Ice"):
        a //= 2
    return max(1, a)


def _defense(dfn: Pokemon, defender_types: list, physical: bool, stage: int, crit: bool, move: dict,
             weather: str, mold_breaker: bool) -> int:
    if crit:
        stage = min(stage, 0)            # a crit ignores the defender's stat boosts
    d = int(dfn.stats["Def" if physical else "SpD"] * stage_multiplier(stage))
    if move["name"] in ("Explosion", "Selfdestruct", "Self-Destruct"):
        d //= 2                          # Gen 4: these halve the target's Defense
    if not physical and weather == "Sandstorm" and "Rock" in defender_types:
        d = d * 3 // 2
    if not mold_breaker:
        if physical and dfn.ability == "Marvel Scale" and status_kind(dfn.status) != "OK":
            d = d * 3 // 2
        if not physical and dfn.ability == "Flower Gift" and weather == "Sun":
            d = d * 3 // 2
    item, num = dfn.held_item_name, dfn.species_id
    if physical and item == "Metal Powder" and num == 132:      # Ditto
        d *= 2
    if not physical and item == "Deep Sea Scale" and num == 366:
        d *= 2
    if not physical and item == "Soul Dew" and num in (380, 381):
        d = d * 3 // 2
    return max(1, d)


def _power(att: Pokemon, dfn: Pokemon, move: dict, power: int, mtype: str, physical: bool,
           mold_breaker: bool) -> int:
    ability, item = att.ability, att.held_item_name
    if ability == "Technician" and power <= 60:
        power = power * 3 // 2
    if PINCH.get(ability) == mtype and (att.hp or 0) <= (att.max_hp or 0) // 3:
        power = power * 3 // 2           # Torrent etc. at 1/3 HP or less
    if ability == "Iron Fist" and "punch" in move["flags"]:
        power = power * 6 // 5
    if ability == "Reckless" and (move["recoil"] or move["name"] in ("Jump Kick", "Hi Jump Kick", "High Jump Kick")):
        power = power * 6 // 5
    if not mold_breaker:
        if dfn.ability == "Heatproof" and mtype == "Fire":
            power //= 2
        if dfn.ability == "Dry Skin" and mtype == "Fire":
            power = power * 5 // 4
    if (item == "Muscle Band" and physical) or (item == "Wise Glasses" and not physical):
        power = power * 11 // 10
    if TYPE_ITEMS.get(item) == mtype:
        power = power * 6 // 5
    if item in ORBS and att.species_id == ORBS[item][0] and mtype in ORBS[item][1]:
        power = power * 6 // 5
    return max(1, power)


def hit_rolls(att: Pokemon, dfn: Pokemon, settings: dict, attacker_types: list, defender_types: list,
              attacker_stages: dict | None = None, defender_stages: dict | None = None,
              field: Field | None = None, defender_side: str = "foe", power: int | None = None,
              berry: bool = True) -> list[int]:
    """The 16 possible damage values of one hit (one per random roll, 85% to 100%).
    berry=False when a resist berry has already been eaten."""
    move, mtype = settings["move"], settings["type"]
    physical, crit = settings["category"] == "Physical", settings["crit"]
    power = settings["power"] if power is None else power
    weather = current_weather(field, att, dfn)
    mold = att.ability == "Mold Breaker"
    typeless = move["name"] == "Struggle"            # Gen 4 Struggle has no type
    effs = [] if typeless else _effectiveness(mtype, defender_types, att.ability == "Scrappy")
    total = 1.0
    for e in effs:
        total *= e
    st_a = (attacker_stages or {}).get("Atk" if physical else "SpA", 0)
    st_d = (defender_stages or {}).get("Def" if physical else "SpD", 0)

    a = _attack(att, dfn, physical, st_a, crit, mtype, weather, mold)
    d = _defense(dfn, defender_types, physical, st_d, crit, move, weather, mold)
    bp = _power(att, dfn, move, power, mtype, physical, mold)

    base = (2 * att.level // 5 + 2) * bp * a // d // 50
    if physical and status_kind(att.status) == "Burned" and att.ability != "Guts":
        base //= 2
    side = getattr(field, defender_side) if field is not None else None
    if side is not None and not crit and ((physical and side.reflect) or (not physical and side.light_screen)):
        base //= 2
    if (weather == "Rain" and mtype == "Water") or (weather == "Sun" and mtype == "Fire"):
        base = base * 3 // 2
    if (weather == "Rain" and mtype == "Fire") or (weather == "Sun" and mtype == "Water"):
        base //= 2
    base += 2
    if crit:
        base *= 3 if att.ability == "Sniper" else 2
    if att.held_item_name == "Life Orb":
        base = base * 13 // 10

    stab = not typeless and mtype in attacker_types
    item = dfn.held_item_name
    rolls = []
    for r in range(85, 101):
        x = base * r // 100
        if stab:
            x = x * 2 if att.ability == "Adaptability" else x * 3 // 2
        for e in effs:
            x = int(x * e)
        if total > 1:
            if not mold and dfn.ability in ("Filter", "Solid Rock"):
                x = x * 3 // 4
            if att.held_item_name == "Expert Belt":
                x = x * 6 // 5
            if berry and RESIST_BERRIES.get(item) == mtype and mtype != "Normal":
                x //= 2
        if total < 1 and att.ability == "Tinted Lens":
            x *= 2
        if berry and item == "Chilan Berry" and mtype == "Normal":
            x //= 2
        rolls.append(max(1, x))
    return rolls


# ---------------------------------------------------------------- hits to KO

def _combine(a: dict, b: dict) -> dict:
    """Distribution of the sum of two independent damage distributions ({damage: chance})."""
    out = defaultdict(float)
    for x, p in a.items():
        for y, q in b.items():
            out[x + y] += p * q
    return dict(out)


def _from_rolls(rolls: list[int]) -> dict:
    out = defaultdict(float)
    for r in rolls:
        out[r] += 1 / len(rolls)
    return dict(out)


def _hit_counts(hits: tuple) -> dict:
    """{number of hits: chance}. 2-5 hit moves: 2 or 3 hits 37.5% each, 4 or 5 hits 12.5%."""
    lo, hi = hits
    if lo == hi:
        return {lo: 1.0}
    return {2: 0.375, 3: 0.375, 4: 0.125, 5: 0.125}


def end_of_turn(dfn: Pokemon, defender_types: list, weather: str, turn: int) -> tuple[int, list]:
    """HP the defender gains (+) or loses (-) at the end of a turn, and what caused it.
    turn counts from 1 (Toxic gets worse each turn)."""
    mx, ability, item = dfn.max_hp or 1, dfn.ability, dfn.held_item_name
    status = status_kind(dfn.status)
    magic_guard = ability == "Magic Guard"
    part = lambda n: max(1, mx // n)
    change, why = 0, []
    if weather == "Sandstorm" and not magic_guard and ability != "Sand Veil" \
            and not {"Rock", "Ground", "Steel"} & set(defender_types):
        change -= part(16); why.append("sandstorm -1/16")
    if weather == "Hail":
        if ability == "Ice Body":
            change += part(16); why.append("Ice Body +1/16")
        elif not magic_guard and ability != "Snow Cloak" and "Ice" not in defender_types:
            change -= part(16); why.append("hail -1/16")
    if weather == "Rain" and ability == "Rain Dish":
        change += part(16); why.append("Rain Dish +1/16")
    if ability == "Dry Skin" and weather == "Rain":
        change += part(8); why.append("Dry Skin +1/8")
    if ability == "Dry Skin" and weather == "Sun" and not magic_guard:
        change -= part(8); why.append("Dry Skin -1/8")
    if item == "Leftovers":
        change += part(16); why.append("Leftovers +1/16")
    if item == "Black Sludge":
        if "Poison" in defender_types:
            change += part(16); why.append("Black Sludge +1/16")
        elif not magic_guard:
            change -= part(8); why.append("Black Sludge -1/8")
    if status in ("Poisoned", "Toxic") and ability == "Poison Heal":
        change += part(8); why.append("Poison Heal +1/8")
    elif not magic_guard:
        if status == "Poisoned":
            change -= part(8); why.append("poison -1/8")
        elif status == "Toxic":
            change -= max(1, mx * turn // 16); why.append("Toxic -1/16 more each turn")
        elif status == "Burned":
            change -= part(16) if ability == "Heatproof" else part(8)
            why.append("burn -1/8")
    return change, why


def calculate(att: Pokemon, dfn: Pokemon, settings: dict, attacker_types: list, defender_types: list,
              attacker_stages: dict | None = None, defender_stages: dict | None = None,
              field: Field | None = None, defender_side: str = "foe") -> Result | None:
    """Damage of one use of a move and the hits to KO, or None for status moves."""
    move = settings["move"]
    if settings["category"] == "Status" and settings["fixed"] is None:
        return None
    mx, hp = dfn.max_hp or 1, dfn.hp if dfn.hp is not None else (dfn.max_hp or 1)
    weather = current_weather(field, att, dfn)
    fixed, name = settings["fixed"], move["name"]

    # damage of the next use, given the defender's HP and how many uses came before
    if fixed is not None:
        if fixed == 0:
            return Result(0, 0, mx, no_effect="no effect")
        if name == "Super Fang":
            use = lambda h, n: {max(1, h // 2): 1.0}
        elif name == "Endeavor":
            use = lambda h, n: {max(0, h - (att.hp or 0)): 1.0}
        elif name in OHKO:
            use = lambda h, n: {h: 1.0}
        elif name == "Psywave":         # level x 50-150%, every value equally likely
            values = [max(1, att.level * r // 100) for r in range(50, 151)]
            psy = _from_rolls(values)
            use = lambda h, n: psy
        else:
            use = lambda h, n: {fixed: 1.0}
    else:
        effs = _effectiveness(settings["type"], defender_types, att.ability == "Scrappy")
        total = 1.0
        for e in effs:
            total *= e
        if name != "Struggle":
            why = _no_effect(move, settings["type"], total, dfn, att.ability == "Mold Breaker")
            if why:
                return Result(0, 0, mx, no_effect=why)
        args = (att, dfn, settings, attacker_types, defender_types, attacker_stages, defender_stages,
                field, defender_side)
        powers = [settings["power"] * k for k in (1, 2, 3)] if name == "Triple Kick" else None

        def one_use(berry: bool) -> dict:
            if powers:                   # Triple Kick: 10, then 20, then 30 power
                dist = {0: 1.0}
                for i, p in enumerate(powers):
                    dist = _combine(dist, _from_rolls(hit_rolls(*args, power=p, berry=berry and i == 0)))
                return dist
            first = _from_rolls(hit_rolls(*args, berry=berry))
            later = _from_rolls(hit_rolls(*args, berry=False))
            out = defaultdict(float)
            for count, chance in _hit_counts(settings["hits"]).items():
                dist = first
                for _ in range(count - 1):
                    dist = _combine(dist, later)
                for d, p in dist.items():
                    out[d] += p * chance
            return dict(out)

        first_use, later_use = one_use(True), one_use(False)
        use = lambda h, n: first_use if n == 1 else later_use

    now = use(hp, 1)
    result = Result(min(now), max(now), mx)

    # hits to KO: follow every possible HP the defender could be left on
    sash = dfn.held_item_name == "Focus Sash" and settings["hits"] == (1, 1)
    states, ko = {hp: 1.0}, 0.0
    for n in range(1, MAX_HITS + 1):
        after = defaultdict(float)
        for h, p in states.items():
            for d, q in use(h, n).items():
                left = h - d
                if left <= 0 and sash and h == mx:
                    left = 1                # Focus Sash: survives one hit from full HP
                if left <= 0:
                    ko += p * q
                else:
                    after[left] += p * q
        change, why = end_of_turn(dfn, defender_types, weather, n)
        if n == 1:
            result.notes = why
        states = {}
        for h, p in after.items():
            h2 = min(mx, h + change)
            if h2 <= 0:
                ko += p                     # finished off at the end of the turn
            else:
                states[h2] = states.get(h2, 0.0) + p
        result.chances.append(min(1.0, ko))
        if result.ko_hits is None and ko >= 0.5 - 1e-9:
            result.ko_hits, result.ko_chance = n, min(1.0, ko)
        if ko >= 0.9995 or not states:
            break
    return result
