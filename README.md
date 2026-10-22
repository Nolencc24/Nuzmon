# SoulSilver Tracker (starter)

Reads your party and the opponent's Pokémon straight out of DeSmuME's memory and shows
stats, IVs, EVs, HP, nature, ability, moves and Hidden Power in a separate window.

```
DeSmuME's memory ──(memreader.py reads it from outside)──> decoder.py ──> window
```
Nothing runs inside the emulator, so fast forward stays smooth. The Lua script is still
included as a fallback (`--lua`).

## Files

| File | What it does |
|---|---|
| `memreader.py` | Finds DeSmuME, locates the DS's RAM inside it, and reads the party/enemy bytes. |
| `tracker.lua` | Fallback only: dumps the same bytes to `ss_dump.txt` from inside DeSmuME (slows fast forward). |
| `decoder.py` | Decrypts and parses Gen 4 Pokémon data (checksum, unshuffle, battle stats). |
| `tracker.py` | The window. Polls DeSmuME 4× a second and redraws when anything changes. |
| `names.py` | Species, move, ability and nature names. |
| `test_decoder.py` | Checks the decoder against real Gen 4 Pokémon. |

## Setup (Windows)

1. Install Python 3.10+ and run `pip install -r requirements.txt`
2. Put all these files in one folder.
3. Check the decoder works: `python test_decoder.py`
4. See the window with sample data: `python tracker.py --demo`

## Running it

1. Open SoulSilver in DeSmuME and load your save (get past the title screen).
2. Run `python tracker.py`. It finds DeSmuME by itself; no Lua script needed.

Use 64-bit Python. If DeSmuME runs as administrator, run the tracker as administrator too.
If you have more than one DeSmuME open, pass the right one with `--pid <process id>`
(from Task Manager → Details).

Fallback: load `tracker.lua` in DeSmuME (**Tools → Lua Scripting**) and run `python tracker.py --lua`.

The bottom bar shows how many slots decoded. Every slot shown has passed the game's own
checksum, so if a Pokémon appears, the data is correct.

## Troubleshooting

- **"no SoulSilver/HeartGold RAM was found yet"** — load your save; the tracker locks on once
  you're past the title screen and keeps retrying until then.
- **"Waiting for ss_dump.txt"** (`--lua` mode) — DeSmuME may be writing the file somewhere else. Set
  `OUTPUT_FILE` in `tracker.lua` to a full path (e.g. `C:/tracker/ss_dump.txt`) and run
  `python tracker.py --lua --file C:/tracker/ss_dump.txt`.
- **"0 party slots decoded"** — on the title screen this is normal. In-game, the address is
  wrong for your ROM. Check the game code in the status bar: US SoulSilver is `IPGE`.
  European ROMs are detected automatically in direct mode; in `--lua` mode change
  `BASE_POINTER` to `0x021D110C`.
- **Opponent tab shows an old Pokémon outside battle** — the game leaves the last battle's
  data in memory. Expected for now.

## Things still to verify on real gameplay

- Whether HP (yours and the opponent's) updates live during battle, or only when the battle
  ends. If it lags, the live value lives in a separate battle structure; find it with
  DeSmuME's **Tools → RAM Search** while taking damage.
- Held items are read (`held_item` in `decoder.py`) but shown only as IDs, so not displayed yet.

## References

- Data structure: Project Pokémon, *PKM Structure – Generation 4*
- RAM addresses: yPokeStats by yling (github.com/yling/yPokeStats)
