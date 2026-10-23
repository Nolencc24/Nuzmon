# SoulSilver Tracker

Reads your party and the opponent's Pokémon straight out of DeSmuME's memory and shows
stats, IVs, EVs, HP, nature, ability, moves and Hidden Power. HP updates live during
battle, and whichever Pokémon is out gets the big expanded card.

Nothing runs inside the emulator, so fast forward stays smooth.

## Setup (Windows)

1. Install 64-bit Python 3.10+ and run `pip install -r requirements.txt`
2. Check the decoder works: `python tests/test_decoder.py`
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
    names.py                species / move / ability / nature names
    memreader.py            find DeSmuME and the DS's RAM inside it
    battle.py               live battle HP + which Pokémon is out
    sources.py              data sources the window polls (memory, Lua file, demo)
    samples.py              two real Pokémon for tests and --demo
  ui/
    main_window.py          tabs + status bar; polls the source and feeds every page
    style.py                stylesheet / colors
    widgets.py              reusable Card and Row widgets
    pages/
      battle_page.py        the Battle tab
      blank_page.py         placeholder for unbuilt tabs
tests/test_decoder.py
tools/tracker.lua           Lua fallback (slows fast forward; use only if needed)
```

### Adding a page

1. Create `tracker/ui/pages/my_page.py` with a `QWidget` subclass.
2. If it needs game data, give it `update_data(self, data)`. The window calls it with
   `data["party"]`, `data["enemy"]` (lists of 6 Pokémon or None), `data["party_active"]`
   and `data["enemy_active"]` (index of the Pokémon out in battle, or None).
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
