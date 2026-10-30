# Nuzmon

**A live battle companion for Pokémon SoulSilver and HeartGold.** Nuzmon sits next to
DeSmuME and shows you everything the game hides: exact stats, IVs, EVs, natures, moves
and held items for your party *and* your opponent's, plus a full Gen 4 damage calculator
that updates itself as the battle plays out.

Built for Nuzlocke runs, where a single bad read can cost you a Pokémon for good.

## Why Nuzmon

- **No guesswork.** Know the opponent's real stats and moveset before you commit to a
  switch, not after.
- **Know whether you survive.** Every move shows its damage range, its percentage of HP,
  and how many hits it takes to knock out the target.
- **Zero setup in battle.** Nuzmon reads the game directly. No typing in species, levels
  or HP between turns.
- **Doesn't slow your game down.** Nothing runs inside the emulator, so fast forward stays
  smooth.

## Features

### Your team and the opponent's, decoded
- Every Pokémon's stats, IVs, EVs, nature (with its stat boost and drop highlighted),
  ability, moves with PP, held item and Hidden Power type and power.
- HP updates live during battle, and the Pokémon that's out gets the big card.
- Works for trainer battles and wild encounters, including trainers with several identical
  Pokémon.

### A damage calculator that keeps up with the battle
- **Damage summary for every move**, in both directions:
  `Earthquake  93–109 (39.6–46.4%) · guaranteed 3HKO`
- **Hits to KO you can trust.** It shows the fewest hits with at least a 50% chance to KO,
  starting from the target's *current* HP, and counts what happens between hits: poison,
  Toxic, burn, sandstorm and hail damage, and Leftovers or Black Sludge healing.
- **Follows the battle automatically:** who's out, stat changes (Swords Dance shows as
  Atk +2), held items (a berry being eaten), and the live types of each Pokémon.
- **Gen 4 rules, not modern ones:** the physical/special split by move, Gen 4 base powers,
  and the Gen 4 order of operations and rounding, across all 16 damage rolls.
- **Understands the tricky moves:** Night Shade, Seismic Toss, Super Fang, Psywave and the
  one-hit KO moves; power that depends on the situation (Flail, Eruption, Gyro Ball, Low
  Kick, Return, Fling, Natural Gift, Hidden Power…); and multi-hit moves with their real
  odds.
- **Abilities and items that matter:** Huge Power, Technician, Torrent / Blaze / Overgrow /
  Swarm, Levitate, Wonder Guard, Mold Breaker, Choice items, Life Orb, Expert Belt, plates,
  resist berries, Focus Sash and more.
- **Speed check:** see who moves first at a glance, counting stat stages, paralysis,
  Choice Scarf, Tailwind, Trick Room and weather abilities.
- **Field conditions:** weather, Reflect, Light Screen, Tailwind and Trick Room. Weather
  turns on by itself when a Pokémon with Drizzle, Drought, Sand Stream or Snow Warning
  comes out.

### Plan ahead with "what if"
- Change anything on either side: species, level, IVs, EVs, nature, ability, item, HP
  (as a number or a percentage), status and stat stages. The stats and damage update
  instantly.
- Click any bench Pokémon to see how it would fare.
- One **Reset** button goes back to following the game.

## Requirements

- Windows
- [DeSmuME](https://desmume.org/) running Pokémon SoulSilver or HeartGold
- 64-bit Python 3.10 or newer

## Getting started

1. Install the dependencies:
   ```
   pip install -r requirements.txt
   ```
2. Try it with sample data, no emulator needed:
   ```
   python main.py --demo
   ```
3. Open your game in DeSmuME, load your save (get past the title screen), then run:
   ```
   python main.py
   ```
   Nuzmon finds DeSmuME by itself and locks on once your save is loaded.

If DeSmuME runs as administrator, run Nuzmon as administrator too. With more than one
DeSmuME open, choose one with `--pid <process id>` (Task Manager → Details).

## How it works

Nuzmon is a Python desktop app (Qt, via PySide6) that reads the emulator's memory from the
outside. Nothing is injected into the game.

1. **Find the game.** It locates the DeSmuME process, finds the Nintendo DS's RAM inside it,
   and checks it's looking at SoulSilver or HeartGold.
2. **Read the Pokémon.** Four times a second it copies your party and the opponent's from
   RAM. Gen 4 stores each Pokémon encrypted and shuffled, so Nuzmon decrypts each one,
   verifies its checksum, and decodes stats, IVs, EVs, moves and more.
3. **Follow the battle.** During a battle the game keeps separate live copies of the
   Pokémon that are out, with their current HP, stat stages, types and item. Nuzmon reads
   these to know who's out and what's changed this turn.
4. **Calculate.** Species, move, ability, item and type-chart data comes from Pokémon
   Showdown's Generation 4 data, bundled with the app. The damage calculator runs the Gen 4
   formula over all 16 random rolls, then tracks every HP the target could be left on, turn
   by turn, to work out the chance of each KO.
5. **Show it.** The window only redraws when something actually changes in the game.

The game-reading and calculation code (`tracker/game/`) is kept separate from the
interface (`tracker/ui/`) and has its own tests.

## Good to know

- Single battles only for now. In double battles only one Pokémon per side is followed, and
  spread moves aren't reduced.
- Screens, Tailwind, Trick Room and weather (other than from abilities) are set by hand.
  Nuzmon doesn't read them from the game yet.
- Random critical hits aren't counted in the hits-to-KO chance. Turn on **Crit** on a move
  to see crit damage.

## Troubleshooting

- **"no SoulSilver/HeartGold RAM was found yet"**: load your save. Nuzmon locks on once
  you're past the title screen and keeps retrying until then.
- **Anything else not being found**: run `python main.py --diagnose` and check what it
  reports.
- **Lua fallback**: if direct memory reading doesn't work on your setup, load
  `tools/tracker.lua` in DeSmuME (**Tools → Lua Scripting**, needs `lua51.dll` next to
  `desmume.exe`) and run `python main.py --lua`. This slows down fast forward, so use it
  only if needed.

## For developers

```
main.py               starts the app: picks the data source, opens the window
tracker/game/         reading the game and all the battle math (no UI code)
tracker/data/         Gen 4 reference data (generated JSON; don't edit by hand)
tracker/storage.py    saved user data (SQLite in userdata/, created on first use)
tracker/ui/           the window, shared widgets and the Battle tab
tests/                plain scripts with asserts
tools/build_data/     regenerates tracker/data from Pokémon Showdown (needs Node.js)
```

- **Run the tests:** `for f in tests/test_*.py; do python "$f"; done`
- **Regenerate the game data:** `cd tools/build_data && npm install && npm run build`
- **Change the database layout:** append a new SQL string to `MIGRATIONS` in
  `tracker/storage.py`. Never edit an old one.
- **Add a tab:** create a `QWidget` in `tracker/ui/pages/`, give it `update_data(self, data)`
  if it needs game data, and replace a `("", BlankPage)` entry in `PAGES` in
  `tracker/ui/main_window.py`. `data` holds `party` and `enemy` (6 Pokémon or None each),
  `party_active` and `enemy_active` (index of the Pokémon out, or None), and `battle` (None
  outside battle, else `{"id", "you", "foe"}` with the live battlers; `id` goes up by one
  per battle).

## Credits

- Pokémon data structure: Project Pokémon, *PKM Structure – Generation 4*
- RAM addresses: yPokeStats by yling (github.com/yling/yPokeStats)
- Battle structures: the pret/pokeheartgold decompilation
- Move, species and type data: Pokémon Showdown (via @pkmn/dex and @pkmn/data)
- Field offsets checked against PKHeX

Nuzmon is a fan-made tool and isn't affiliated with Nintendo, Game Freak or The Pokémon
Company.
