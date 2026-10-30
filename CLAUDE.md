# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Nuzmon is a PySide6 desktop app (Windows) that reads Pokémon SoulSilver/HeartGold (Gen 4) party and opponent data straight out of DeSmuME's process memory and shows it live, with a damage calculator on the Battle tab. Nothing runs inside the emulator.

## Commands

```
pip install -r requirements.txt          # PySide6, psutil (64-bit Python 3.10+)
python main.py --demo                    # run the UI with sample data (no emulator needed)
python main.py                           # read a running DeSmuME (auto-detects; --pid N to choose)
python main.py --diagnose                # print what memreader finds in DeSmuME, then exit
python main.py --lua                     # fallback: read ss_dump.txt written by tools/tracker.lua
```

Tests are plain scripts with asserts, not a pytest suite. Each file adds the project root to `sys.path` and exposes `test()`; run one with:

```
python tests/test_stats.py
```

Run all of them with `for f in tests/test_*.py; do python "$f"; done`. There is no linter or build step configured.

Regenerate the Gen 4 reference data (needs Node.js): `cd tools/build_data && npm install && npm run build`.

## Architecture

**Data flow:** `main.py` picks a *source* → `MainWindow` polls it every 250 ms → passes the result to every page that has `update_data(data)`. Pages never touch the emulator themselves.

- **Sources** (`tracker/game/sources.py`): `MemorySource` (default), `FileSource` (Lua dump or `--demo`, which writes a fake dump built from `samples.py`). Both return `(data or None, status message or None)`, with `data is None` meaning "nothing changed". `MemorySource` builds a "shown" tuple and returns None unless something visible changed, so pages only redraw on real changes.
- **`data` dict shape** (documented at the top of `sources.py` and in the README's "Adding a page"): `party`/`enemy` (6 × `Pokemon|None`), `party_active`/`enemy_active` (index or None), `battle` (None, or `{"id", "you", "foe"}` with live `Battler`s, which covers wild Pokémon; `id` goes up by one per battle), and `meta`. `battle` only exists in memory mode.
- **`tracker/game/`** holds all game logic and must stay UI-free:
  - `memreader` finds DeSmuME and the DS RAM base.
  - `decoder` decrypts/unshuffles the 236-byte Gen 4 PKM struct into the `Pokemon` dataclass. A failed checksum gives None.
  - `battle` overrides party HP with live battle copies in RAM (`BattleHP`) and works out who is out (`BattleState`).
  - `stats` handles stat math and *derived* Pokémon: `adjusted`/`with_level` return copies (or the same object when nothing changed), `preview` makes a made-up Pokémon (`.preview = True`), and `from_battler` builds one for wild battlers.
  - `gamedata` looks things up in `tracker/data/*.json`, using the game's own internal IDs so RAM values index it directly.
  - `field` holds the field conditions (`Field`: weather, Trick Room, each `Side`'s Reflect / Light Screen / Tailwind) and `current_weather()` (Cloud Nine / Air Lock cancel it). They're set by hand in the calculator, not read from RAM, and cleared when a battle starts or ends. The exception: when a Pokémon with a weather ability (`ABILITY_WEATHER`: Drizzle, Drought, Sand Stream, Snow Warning) comes out in battle, `InfoPanel._weather_from_switch_ins` sets the weather. If both sides' setters come out at once, `weather_after_switch_ins` lets the slower one win. `stats.speed()` takes `weather` and `tailwind`.
  - `moves.effect(move, user, target, user_stages, target_stages, field, user_side)` works out a move's real power, type, fixed damage (Night Shade, Super Fang, OHKOs… which skip the damage formula) and hit count in the current situation. Moves whose power can't be known (Magnitude, Rollout…) get a typical value and a note.
- **PIDs aren't unique:** a trainer's Pokémon of the same species and level share one PID (Gen 4 derives it from trainer + species + level). Identify team members by **party index** (`party_active`/`enemy_active`, `CalcSide.slot()`/`pin_slot`), not by PID alone. `BattleState._active` tracks which "twin" is out (the same one until it faints, then the next unfainted one), and `BattleHP` keys twins by `(pid, side, slot)`. When each battle copy in RAM last changed is tracked once for everyone (`BattleHP.copies`, timed by an update counter, not the clock), so a twin that just came out can't pick up a leftover copy holding the fainted twin's 0 HP. `BattleState.update` must run before `BattleHP.apply`.
- **Reference vs. saved data:** `tracker/data/*.json` is generated from Pokémon Showdown's Gen 4 data and must not be hand-edited. Data the app writes goes in SQLite through `tracker/storage.py` (`userdata/tracker.db`, git-ignored). To change the schema, **append** a new SQL string to `MIGRATIONS` and never edit an existing one; versioning uses `PRAGMA user_version`.

**Battle tab** (`tracker/ui/pages/battle_page.py` + `damage_calc.py`): `BattlePage` = party `TeamSection` / `InfoPanel` (calculator) / enemy `TeamSection`. The calculator has two `CalcSide`s (You, Foe; Foe is mirrored), each with 4 `MoveRow`s.
- A `CalcSide` follows the live Pokémon until the user edits anything. That *pins* it, and Reset unpins it. A pinned side is either a real Pokémon (tracked by PID + party slot, refreshed from the team each update so HP stays live) or a `preview` by species name. Clicking a bench row (`select`) pins that team member.
- **Hand edits** all live in one `Edits` dataclass per side (`CalcSide.edits`): level, IVs, EVs, HP, nature, status, ability, held item, stat stages. `Edits.apply()` turns the game's Pokémon into `subject()`; starting over is `self.edits = Edits()`. Each edit has a public `set_*` method (`set_level`, `set_stat`, `set_hp`, `set_nature`, `set_status`, `set_ability`, `set_item`, `set_stage`) that goes through `_edit(...)`, which pins and redraws. To add a new kind of edit: add a field to `Edits`, a line in `apply()`, and a `set_*` method.
- **Move rows** show `moves.effect()` for this side's `subject()` against the other side's (`CalcSide.set_target`, fed by `InfoPanel._sides_changed`). They refresh whenever either Pokémon changes. A power or type the user types in is kept until another move is picked. Fixed damage shows in orange and is read-only.
- **Damage** (`tracker/game/damage.py`, UI-free): `calculate(attacker, defender, settings, attacker_types, defender_types, stages…, field, defender_side)` runs the Gen 4 formula over all 16 random rolls (`hit_rolls`), and works out hits to KO from the defender's current HP. It follows every possible HP left, including end-of-turn damage/healing between hits (`end_of_turn`), Focus Sash and resist berries, and reports the fewest hits with a ≥50% KO chance. Random crits aren't counted (the row's Crit toggle forces one). Each `CalcSide` shows `results()` for its moves against the other side in its `summary` label, under the stat stages. Types come from `CalcSide.types()`: the live battle types while out, else the species'. `moves()` gives each row's power, type, category, crit, `fixed` damage (when set, the formula is skipped) and `hits`. Gen 4 notes on how status, abilities and items should affect damage are next to `STATUSES`, `with_ability` and `with_item` in `stats.py`.
- **Live battle values:** when a side's Pokémon is the one out (`_is_out()`), stat stages (`stages()`) and the held item come from the live `Battler` unless edited by hand.
- `CalcSide.subject()` is the Pokémon the side calculates with, and the Battle tab's big "lead" card shows it. Calculator edits emit `subject_changed` → `BattlePage._render` (and the speed line). The big card's editable fields emit `level_edited`, `stat_edited`, `hp_edited`, `nature_edited` and `status_edited`, which `BattlePage` connects to that side's `set_*` methods.
- `_filling` / `emit=False` / `isModified()` guards stop programmatic widget updates from counting as user edits (and pinning the side), and stop live updates from overwriting a box the user is typing in.

**Adding a tab:** create a `QWidget` in `tracker/ui/pages/`, optionally with `update_data(data)`, and replace a `("", BlankPage)` entry in `PAGES` in `tracker/ui/main_window.py`. Shared widgets (Card, Row, `StatEdit`, and the searchable `SearchPicker` subclasses for moves, species, natures, statuses, abilities and items) live in `tracker/ui/widgets.py`, and the stylesheet and colors in `tracker/ui/style.py`.

## Conventions

- Code is written to be beginner-readable: module docstrings that explain the "why" and show usage, short comments on non-obvious lines, `from __future__ import annotations`. Match that style.
- Stat names use the in-memory keys `HP, Atk, Def, Spe, SpA, SpD`. Showdown base stats use lowercase keys (`hp`, `atk`, …), and `stats.SHOWDOWN_KEYS` maps between them.
- Values must be Gen 4's (for example, the physical/special split is per move, and power/types are Gen 4's), not modern ones.
- References for game structures: Project Pokémon's Gen 4 PKM doc, yPokeStats (RAM addresses), pret/pokeheartgold (battle structs), PKHeX (field offsets).
