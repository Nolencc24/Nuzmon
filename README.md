# SoulSilver Tracker

Reads your party and the opponent's Pokémon straight out of DeSmuME's memory and shows
stats, IVs, EVs, HP, nature, ability, moves and Hidden Power. HP updates live during
battle, and whichever Pokémon is out gets the big expanded card. The Battle tab's center
panel is the start of a damage calculator, with searchable move pickers for both sides.

Nothing runs inside the emulator, so fast forward stays smooth.

## Setup (Windows)

1. Install 64-bit Python 3.10+ and run `pip install -r requirements.txt`
2. Check everything works: `python tests/test_decoder.py`, `python tests/test_gamedata.py`,
   `python tests/test_storage.py`
3. See the window with sample data: `python main.py --demo`

## Running it

1. Open SoulSilver in DeSmuME and load your save (get past the title screen).
2. Run `python main.py`. It finds DeSmuME by itself.

If DeSmuME runs as administrator, run the tracker as administrator too. With more than
one DeSmuME open, pick one with `--pid <process id>` (Task Manager → Details).

## Project layout

```
main.py                     start here: picks the data source, opens the window
tracker/
  game/                     reading the game (no UI code)
    decoder.py              decrypt + parse Gen 4 Pokémon data
    gamedata.py             look up moves, species, types, abilities, items (from tracker/data)
    memreader.py            find DeSmuME and the DS's RAM inside it
    battle.py               live battle HP, who is out, live battler stats/stages
    sources.py              data sources the window polls (memory, Lua file, demo)
    samples.py              two real Pokémon for tests and --demo
  data/                     Gen 4 reference data (JSON, generated; don't edit by hand)
  storage.py                saved user data (SQLite in userdata/, created on first use)
  ui/
    main_window.py          tabs + status bar; polls the source and feeds every page
    style.py                stylesheet / colors
    widgets.py              reusable widgets: Card, Row, MovePicker
    pages/
      battle_page.py        the Battle tab (teams)
      damage_calc.py        the damage calculator in the middle of the Battle tab
      blank_page.py         placeholder for unbuilt tabs
tests/                      run each with python tests/<file>.py
tools/
  build_data/               regenerates tracker/data from Pokémon Showdown (needs Node.js)
  tracker.lua               Lua fallback (slows fast forward; use only if needed)
```

### Game data

`tracker/data/*.json` holds Gen 4 moves, species (with forms), the type chart, abilities and
held items, exported from Pokémon Showdown's per-generation data, so values are Gen 4's,
not modern ones. IDs are the game's own, so data read from RAM can be looked up directly
with `tracker.game.gamedata`. The files are committed; to regenerate them:

```
cd tools/build_data
npm install
npm run build
```

### Saved data

Reference data is read-only JSON. Anything the app needs to *remember* (like encounters per
route later) goes in SQLite via `tracker/storage.py`, in `userdata/tracker.db` (git-ignored).
To change the database layout, append a new SQL string to `MIGRATIONS`; never edit an old one.

### Adding a page

1. Create `tracker/ui/pages/my_page.py` with a `QWidget` subclass.
2. If it needs game data, give it `update_data(self, data)`. The window calls it with
   `data["party"]`, `data["enemy"]` (lists of 6 Pokémon or None), `data["party_active"]`
   and `data["enemy_active"]` (index of the Pokémon out in battle, or None), and
   `data["battle"]`: None outside battle, else `{"id", "you", "foe"}` where you/foe are the
   live battlers (works for wild Pokémon) and `id` goes up by one per battle.
3. In `tracker/ui/main_window.py`, replace a `("", BlankPage)` entry in `PAGES` with
   `("My tab", MyPage)`.

## Troubleshooting

- **"no SoulSilver/HeartGold RAM was found yet"**: load your save; the tracker locks on
  once you're past the title screen and keeps retrying until then.
- **Anything else not being found**: run `python main.py --diagnose` and check what it reports.
- **Lua fallback**: load `tools/tracker.lua` in DeSmuME (**Tools → Lua Scripting**, needs
  `lua51.dll` next to `desmume.exe`) and run `python main.py --lua`.

## References

- Data structure: Project Pokémon, *PKM Structure – Generation 4*
- RAM addresses: yPokeStats by yling (github.com/yling/yPokeStats)
- Battle structures: pret/pokeheartgold decompilation
- Move/species/type data: Pokémon Showdown (via @pkmn/dex and @pkmn/data)
- Field offsets checked against PKHeX
