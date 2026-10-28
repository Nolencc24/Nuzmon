"""
Field conditions for the calculator: weather, Trick Room, and each side's screens and
Tailwind (Gen 4 rules). These aren't read from the game yet; they're set by hand, except
that weather abilities (Drizzle, Drought...) set the weather when their Pokémon comes out.

    field = Field(weather="Rain")
    field.you.reflect = True
    current_weather(field, user, target)   # "None" if either has Cloud Nine / Air Lock

What they do (the damage formula, once written, should apply the damage parts):
  * Rain: Water moves x1.5, Fire x0.5. Sun: the reverse. Swift Swim / Chlorophyll double
    Speed. Weather Ball becomes 100 power of the weather's type; Solar Beam is halved in
    any weather but sun.
  * Sandstorm: Rock types get x1.5 Sp. Def; everything but Rock/Ground/Steel loses 1/16 max
    HP each turn. Hail: everything but Ice loses 1/16 each turn.
  * Reflect / Light Screen: physical / special damage to that side halved (not on crits).
  * Tailwind: that side's Speed doubled (Gen 4: 3 turns). Trick Room: slower moves first.
"""

from __future__ import annotations

from dataclasses import dataclass, field

WEATHERS = ["None", "Rain", "Sun", "Sandstorm", "Hail"]
WEATHER_TYPES = {"Rain": "Water", "Sun": "Fire", "Sandstorm": "Rock", "Hail": "Ice"}   # for Weather Ball
WEATHER_SPEED = {"Rain": "Swift Swim", "Sun": "Chlorophyll"}                         # x2 Speed in that weather
NO_WEATHER_ABILITIES = {"Cloud Nine", "Air Lock"}

# Abilities that set the weather when their Pokémon comes out (in Gen 4 the weather then
# lasts until something else changes it). Gen 4 has few of these: Kyogre, Groudon,
# Tyranitar, Hippopotas / Hippowdon, Snover / Abomasnow.
ABILITY_WEATHER = {"Drizzle": "Rain", "Drought": "Sun", "Sand Stream": "Sandstorm", "Snow Warning": "Hail"}


@dataclass
class Side:
    """Conditions on one side of the field."""
    reflect: bool = False
    light_screen: bool = False
    tailwind: bool = False


@dataclass
class Field:
    weather: str = "None"          # one of WEATHERS
    trick_room: bool = False
    you: Side = field(default_factory=Side)
    foe: Side = field(default_factory=Side)


def weather_after_switch_ins(weather: str, entering: list) -> tuple[str, object]:
    """The weather after these Pokémon come out at the same time, and which one set it
    (None if none of them did). entering: [(Pokémon, its Speed), ...].

    Abilities activate fastest first, so when two weather setters come out together (say
    Kyogre and Groudon), the faster one's weather goes up first and the slower one's
    replaces it: the slowest setter wins. On a Speed tie the game picks at random; here
    the one listed last wins.
    """
    setter = None
    for mon, _spe in sorted(entering, key=lambda pair: -pair[1]):   # fastest first
        new = ABILITY_WEATHER.get(mon.ability) if mon is not None else None
        if new:
            weather, setter = new, mon
    return weather, setter


def current_weather(f: Field | None, *mons) -> str:
    """The weather in effect: f.weather, unless a Pokémon out has Cloud Nine or Air Lock."""
    if f is None or any(m is not None and m.ability in NO_WEATHER_ABILITIES for m in mons):
        return "None"
    return f.weather
