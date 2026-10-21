# SoulSilver Tracker (starter)

Reads your party and the opponent's Pokémon straight out of DeSmuME's memory and shows
stats, IVs, EVs, HP, nature, ability, moves and Hidden Power in a separate window.

```
DeSmuME ──(tracker.lua dumps raw bytes)──> ss_dump.txt ──(tracker.py decrypts)──> window
```

## Files

| File | What it does |
|---|---|
| `tracker.lua` | Runs inside DeSmuME. Writes the encrypted party/enemy bytes to `ss_dump.txt` 4× a second. |
| `decoder.py` | Decrypts and parses Gen 4 Pokémon data (checksum, unshuffle, battle stats). |
| `tracker.py` | The window. Watches `ss_dump.txt` and redraws when it changes. |
| `names.py` | Species, move, ability and nature names. |
| `test_decoder.py` | Checks the decoder against real Gen 4 Pokémon. |

## Setup (Windows)

1. Install Python 3.10+ and run `pip install -r requirements.txt`
2. Put all these files in one folder.
3. Check the decoder works: `python test_decoder.py`
4. See the window with sample data: `python tracker.py --demo`

## Running it

1. Open SoulSilver in DeSmuME and load your save (get past the title screen).
2. **Tools → Lua Scripting → New Lua Script Window**, browse to `tracker.lua`, click **Run**.
   A small "tracker" label appears in the corner of the game screen.
3. Run `python tracker.py`.

The bottom bar shows how many slots decoded. Every slot shown has passed the game's own
checksum, so if a Pokémon appears, the data is correct.

## Troubleshooting

- **"Waiting for ss_dump.txt"** — DeSmuME may be writing the file somewhere else. Set
  `OUTPUT_FILE` in `tracker.lua` to a full path (e.g. `C:/tracker/ss_dump.txt`) and run
  `python tracker.py --file C:/tracker/ss_dump.txt`.
- **"0 party slots decoded"** — on the title screen this is normal. In-game, the address is
  wrong for your ROM. Check the game code printed in the Lua console: US SoulSilver is
  `IPGE`. For a European ROM change `BASE_POINTER` to `0x021D110C`.
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
