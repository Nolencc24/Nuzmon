"""
Gen 4 reference data: moves, species, types, abilities, items.

Loaded from tracker/data/*.json, which are generated from Pokémon Showdown by
tools/build_data (see the README there). IDs are the game's own internal IDs, so
values read from RAM can be looked up directly.

    from tracker.game import gamedata
    gamedata.move(85)["power"]                  # Thunderbolt -> 95
    gamedata.move_by_name("Thunderbolt")["id"]  # -> 85
    gamedata.species(479, form=2)["types"]      # Rotom-Wash -> ["Electric", "Water"]
    gamedata.effectiveness("Ground", ["Electric", "Flying"])  # -> 0.0
"""

from __future__ import annotations

import json
import os
from functools import cache

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

# Natures in game order (PID % 25). Not part of the Showdown export.
NATURES = ["Hardy", "Lonely", "Brave", "Adamant", "Naughty", "Bold", "Docile", "Relaxed",
           "Impish", "Lax", "Timid", "Hasty", "Serious", "Jolly", "Naive", "Modest", "Mild",
           "Quiet", "Bashful", "Rash", "Calm", "Gentle", "Sassy", "Careful", "Quirky"]


@cache
def _load(name: str):
    with open(os.path.join(DATA_DIR, name), encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------- moves

@cache
def _moves() -> dict[int, dict]:
    return {int(k): {"id": int(k), **v} for k, v in _load("moves.json").items()}


@cache
def _moves_by_name() -> dict[str, dict]:
    return {m["name"].lower(): m for m in _moves().values()}


def move(move_id: int) -> dict | None:
    """Full data for one move by in-game ID, or None."""
    return _moves().get(move_id)


def move_by_name(name: str) -> dict | None:
    return _moves_by_name().get(name.strip().lower())


def move_name(move_id: int) -> str:
    m = move(move_id)
    return m["name"] if m else f"Move #{move_id}"


@cache
def all_move_names() -> list[str]:
    """Every Gen 4 move name, alphabetical (for pickers)."""
    return sorted(m["name"] for m in _moves().values())


# ---------------------------------------------------------------- species

def species_name(num: int) -> str:
    entry = _load("species.json")["by_num"].get(str(num))
    return entry["name"] if entry else f"#{num}"


def species(num: int, form: int = 0) -> dict | None:
    """Base stats, types, abilities... for a species and form (form index as stored in the game)."""
    data = _load("species.json")
    entry = data["by_num"].get(str(num))
    if entry is None:
        return None
    forms = entry["forms"]
    name = forms[form] if 0 <= form < len(forms) and forms[form] else entry["name"]
    return {"name": name, **data["by_name"][name]}


def species_forms(num: int) -> list:
    """Form names in the game's form order (index = form number stored in the Pokémon)."""
    entry = _load("species.json")["by_num"].get(str(num))
    return entry["forms"] if entry else []


@cache
def all_species_names() -> list[str]:
    """Every Gen 4 species and stat-changing form, alphabetical (for pickers)."""
    return sorted(_load("species.json")["by_name"])


def species_by_name(name: str) -> dict | None:
    s = _load("species.json")["by_name"].get(name)
    return {"name": name, **s} if s else None


# ---------------------------------------------------------------- types

def types() -> list[str]:
    return sorted(_load("types.json"))


def effectiveness(attack_type: str, defender_types: list[str]) -> float:
    """Type multiplier, e.g. effectiveness("Fire", ["Grass", "Steel"]) -> 4.0."""
    chart = _load("types.json").get(attack_type)
    if chart is None:   # "???" (Curse) and unknown types are neutral
        return 1.0
    result = 1.0
    for t in defender_types:
        result *= chart.get(t, 1.0)
    return result


# ---------------------------------------------------------------- abilities / items

def ability_name(ability_id: int) -> str:
    return _load("abilities.json").get(str(ability_id), f"Ability #{ability_id}")


def item(item_id: int) -> dict | None:
    """Battle-relevant held items only (others return None)."""
    return _load("items.json").get(str(item_id))


def item_name(item_id: int) -> str | None:
    if item_id == 0:
        return None
    i = item(item_id)
    return i["name"] if i else f"Item #{item_id}"
