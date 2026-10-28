"""
Stat math (Gen 3-5 formula) and Pokémon built for the calculator.

    with_level(mon, 50)                 the same Pokémon with stats recalculated at level 50
    adjusted(mon, ivs={"Spe": 31})      ... or with some IVs / EVs (or the nature) changed
    with_hp(mon, 20)                    ... or with 20 current HP
    with_status(mon, "Burned")          ... or with a status condition
    with_ability(mon, "Torrent")        ... or with another ability
    with_item(mon, "Leftovers")         ... or holding another item
    preview("Garchomp", 40, moves)      a made-up Pokémon (IVs 31, EVs 0, neutral nature)
    from_battler(battler)               a Pokémon built from live battle data (wild Pokémon)
"""

from __future__ import annotations

import dataclasses

from . import gamedata
from .decoder import STAT_NAMES, Pokemon, hidden_power_of
from .field import WEATHER_SPEED

NATURE_STATS = ["Atk", "Def", "Spe", "SpA", "SpD"]   # order used by the nature table
SHOWDOWN_KEYS = {"HP": "hp", "Atk": "atk", "Def": "def", "Spe": "spe", "SpA": "spa", "SpD": "spd"}
PREVIEW_IV, PREVIEW_EV, PREVIEW_NATURE = 31, 0, "Hardy"


def nature_effect(nature: str) -> tuple[str | None, str | None]:
    """(boosted stat, lowered stat), or (None, None) for neutral natures."""
    n = gamedata.NATURES.index(nature)
    up, down = n // 5, n % 5
    return (None, None) if up == down else (NATURE_STATS[up], NATURE_STATS[down])


def calc_stats(base: dict, ivs: dict, evs: dict, level: int, nature: str, species_num: int = 0) -> dict:
    """Actual stats from base stats (Showdown keys hp/atk/...), IVs, EVs, level and nature."""
    up, down = nature_effect(nature)
    out = {}
    for stat in STAT_NAMES:
        core = (2 * base[SHOWDOWN_KEYS[stat]] + ivs[stat] + evs[stat] // 4) * level // 100
        if stat == "HP":
            out[stat] = 1 if species_num == 292 else core + level + 10     # Shedinja always has 1 HP
        else:
            value = core + 5
            if stat == up:
                value = value * 110 // 100
            elif stat == down:
                value = value * 90 // 100
            out[stat] = value
    return out


def base_stats_of(mon: Pokemon) -> dict | None:
    sp = gamedata.species(mon.species_id, mon.form)
    return sp["base_stats"] if sp else None


IV_MAX, EV_MAX, EV_TOTAL_MAX = 31, 252, 510


def adjusted(mon: Pokemon, level: int | None = None, ivs: dict | None = None,
             evs: dict | None = None, nature: str | None = None) -> Pokemon:
    """A copy of mon with a different level, nature and/or some IVs/EVs changed, stats (and
    Hidden Power) recalculated. HP keeps the same percentage. Returns mon itself if nothing
    changes.

    ivs/evs only need the stats that change, e.g. adjusted(mon, ivs={"Spe": 31}).
    """
    level = max(1, min(100, level or mon.level or 1))
    nature = nature or mon.nature
    new_ivs = {**mon.ivs, **{k: max(0, min(IV_MAX, v)) for k, v in (ivs or {}).items()}}
    new_evs = {**mon.evs, **{k: max(0, min(EV_MAX, v)) for k, v in (evs or {}).items()}}
    if level == mon.level and nature == mon.nature and new_ivs == mon.ivs and new_evs == mon.evs:
        return mon
    base = base_stats_of(mon)
    if base is None:
        return mon
    stats = calc_stats(base, new_ivs, new_evs, level, nature, mon.species_id)
    old_max = mon.max_hp or stats["HP"]
    hp = stats["HP"] if mon.hp is None else round((mon.hp or 0) * stats["HP"] / old_max)
    if mon.hp:                       # don't let a scaled-down Pokémon look fainted
        hp = max(hp, 1)
    return dataclasses.replace(mon, level=level, nature=nature, ivs=new_ivs, evs=new_evs, stats=stats,
                               max_hp=stats["HP"], hp=hp, hidden_power=hidden_power_of(new_ivs))


# Major statuses, spelled like Pokemon.status ("OK" = healthy; sleep can also be "Asleep (2)",
# with the turns left). For the damage calculator later: a burn halves the attacker's Atk
# for physical moves, and at the end of each turn Poisoned and Burned lose 1/8 of max HP,
# Toxic n/16 on its nth turn. Both change how many hits it takes to KO.
STATUSES = ["OK", "Poisoned", "Toxic", "Burned", "Paralyzed", "Asleep", "Frozen"]


def status_kind(status: str | None) -> str:
    """The status without extras, one of STATUSES: "Asleep (2)" -> "Asleep", None -> "OK"."""
    s = (status or "OK").split(" (")[0]
    return s if s in STATUSES else "OK"


def with_status(mon: Pokemon, status: str) -> Pokemon:
    """A copy of mon with another status (one of STATUSES). Returns mon itself if unchanged."""
    return mon if status == mon.status else dataclasses.replace(mon, status=status)


def with_ability(mon: Pokemon, ability: str) -> Pokemon:
    """A copy of mon with another ability. Returns mon itself if unchanged.

    For the damage calculator later, Gen 4 abilities that change damage include:
      * Torrent / Blaze / Overgrow / Swarm: Water / Fire / Grass / Bug moves x1.5 power
        when HP <= 1/3 of max HP (so it depends on current HP, which can be edited)
      * Huge Power / Pure Power: Atk x2. Hustle: Atk x1.5. Guts: Atk x1.5 with a status
        (and a burn no longer halves Atk). Technician: moves with power <= 60 x1.5
      * Levitate: immune to Ground. Thick Fat: Fire/Ice damage halved. Filter / Solid Rock:
        super-effective damage x0.75. Wonder Guard: only super-effective moves hit
      * Intimidate: the foe's Atk -1 when it comes in (shows up in the stat stages)
    """
    return mon if ability == mon.ability else dataclasses.replace(mon, ability=ability)


def with_item(mon: Pokemon, item: str | None) -> Pokemon:
    """A copy of mon holding another item (None or "" = nothing). Returns mon itself if
    unchanged.

    For the damage calculator later: Choice Band / Choice Specs x1.5 Atk / SpA, Life Orb
    x1.3 damage, Expert Belt x1.2 super-effective damage, type-boosting items (Charcoal,
    Mystic Water, plates...) x1.2 for their type, Muscle Band / Wise Glasses x1.1, Light
    Ball (Pikachu) and Thick Club (Cubone/Marowak) x2 Atk, resist berries halve one
    super-effective hit, and Leftovers / Black Sludge heal 1/16 per turn.
    """
    item = item or None
    if item == mon.held_item_name:
        return mon
    
    return dataclasses.replace(mon, held_item_name=item, held_item=gamedata.item_id(item))


# Held items that change Speed (Quick Powder only works for Ditto)
SPEED_ITEMS = {"Choice Scarf": 1.5, "Iron Ball": 0.5, "Macho Brace": 0.5, "Power Weight": 0.5,
               "Power Bracer": 0.5, "Power Belt": 0.5, "Power Lens": 0.5, "Power Band": 0.5,
               "Power Anklet": 0.5}


def stage_multiplier(stage: int) -> float:
    """Stat stage -6..+6 as a multiplier: +1 = 3/2, +2 = 4/2, -1 = 2/3, ..."""
    return max(2, 2 + stage) / max(2, 2 - stage)


def speed(mon: Pokemon, stage: int = 0, weather: str = "None", tailwind: bool = False) -> int:
    """Speed used for turn order: the Spe stat with its stat stage, then abilities (Swift
    Swim in rain, Chlorophyll in sun, Quick Feet with a status), held items (Choice Scarf,
    Iron Ball... see SPEED_ITEMS), Tailwind (x2), then paralysis (a quarter in Gen 4, but
    not with Quick Feet). Not counted: Unburden and Slow Start, which depend on the turn."""
    spe = int(mon.stats.get("Spe", 0) * stage_multiplier(stage))
    status = status_kind(mon.status)
    if WEATHER_SPEED.get(weather) == mon.ability:
        spe *= 2
    quick_feet = mon.ability == "Quick Feet" and status != "OK"
    if quick_feet:
        spe = spe * 3 // 2
    spe = int(spe * SPEED_ITEMS.get(mon.held_item_name, 1))
    if mon.held_item_name == "Quick Powder" and mon.species_id == 132:     # Ditto
        spe *= 2
    if tailwind:
        spe *= 2
    if status == "Paralyzed" and not quick_feet:
        spe //= 4
    return spe


def with_hp(mon: Pokemon, hp: int, of_max: int | None = None) -> Pokemon:
    """A copy of mon with this much current HP (clamped to 0-max). Returns mon itself if
    nothing changes.

    of_max: the max HP that hp was picked against. If mon's max HP is different (its level
    or HP IV/EVs changed since), hp is scaled so it keeps the same percentage.
    """
    mx = mon.max_hp
    if not mx:
        return mon
    if of_max and of_max != mx:
        hp = max(1, round(hp * mx / of_max)) if hp else 0
    hp = max(0, min(mx, hp))
    return mon if hp == mon.hp else dataclasses.replace(mon, hp=hp)


def hp_percent(hp: int, max_hp: int) -> int:
    """HP as a whole percentage. Never shows 0% while the Pokémon is still standing, or
    100% when it has taken damage."""
    if not hp or not max_hp:
        return 0
    return max(1, min(100 if hp >= max_hp else 99, round(100 * hp / max_hp)))


def hp_from_percent(pct: int, max_hp: int) -> int:
    """Current HP for a percentage of max_hp (at least 1 HP unless pct is 0)."""
    if pct <= 0:
        return 0
    return max(1, min(max_hp, round(pct * max_hp / 100)))


def with_level(mon: Pokemon, level: int) -> Pokemon:
    """A copy of mon at another level, with stats recalculated (HP keeps the same percentage)."""
    return adjusted(mon, level=level)


def preview(species_name: str, level: int, moves: list | None = None) -> Pokemon | None:
    """A made-up Pokémon of this species for the calculator: IVs 31, EVs 0, neutral nature.

    moves: [(name, pp), ...] to show on it (e.g. the moves picked in the calculator).
    """
    sp = gamedata.species_by_name(species_name)
    if sp is None:
        return None
    forms = gamedata.species_forms(sp["num"])
    form = forms.index(species_name) if species_name in forms else 0
    level = max(1, min(100, level))
    ivs = {s: PREVIEW_IV for s in STAT_NAMES}
    evs = {s: PREVIEW_EV for s in STAT_NAMES}
    stats = calc_stats(sp["base_stats"], ivs, evs, level, PREVIEW_NATURE, sp["num"])
    moves = [(n, pp) for n, pp in (moves or []) if n]
    return Pokemon(
        pid=0, species_id=sp["num"], species=species_name, held_item=0, tid=0, sid=0, exp=0,
        friendship=0, ability=sp["abilities"][0], evs=evs, ivs=ivs, moves=moves,
        move_ids=[gamedata.move_by_name(n)["id"] for n, _ in moves if gamedata.move_by_name(n)],
        is_egg=False, nature=PREVIEW_NATURE, shiny=False, gender="", hidden_power=hidden_power_of(ivs),
        pokerus=0, form=form, level=level, status="OK", hp=stats["HP"], max_hp=stats["HP"],
        stats=stats, preview=True,
    )


def from_battler(b) -> Pokemon:
    """A Pokémon built from live battle data, for Pokémon that aren't in any party list
    (wild Pokémon). EVs aren't in the battle data; wild Pokémon have none anyway."""
    evs = {s: 0 for s in STAT_NAMES}
    return Pokemon(
        pid=b.pid, species_id=b.species_id, species=b.species, held_item=0, tid=0, sid=0, exp=0,
        friendship=0, ability=b.ability, evs=evs, ivs=b.ivs, moves=list(b.moves), move_ids=list(b.move_ids),
        is_egg=False, nature=b.nature, shiny=b.shiny, gender="", hidden_power=b.hidden_power, pokerus=0,
        form=b.form, level=b.level, status=b.status, hp=b.hp, max_hp=b.max_hp,
        stats={"HP": b.max_hp, **b.stats}, in_battle=True, held_item_name=b.item,
    )


def form_name(mon: Pokemon) -> str:
    """Species name including the form, e.g. "Rotom-Wash" (what the species picker shows)."""
    sp = gamedata.species(mon.species_id, mon.form)
    return sp["name"] if sp else mon.species
