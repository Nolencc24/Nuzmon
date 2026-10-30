"""
Gen 4 (DPPt / HGSS) Pokémon decoder.

Follows the Project Pokémon "PKM Structure - Generation 4" doc:
  * bytes 0x00-0x07  unencrypted header (PID, unused, checksum)
  * bytes 0x08-0x87  4 shuffled 32-byte blocks, XOR-encrypted, PRNG seeded by checksum
  * bytes 0x88-0xEB  party/battle stats, XOR-encrypted, PRNG seeded by PID, NOT shuffled
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

from .gamedata import NATURES, ability_name, item_name, move_name, species_name

PARTY_SIZE = 236   # 0xEC
STORED_SIZE = 136  # 0x88
BLOCK_SIZE = 32

# "Block Order" column from the doc, indexed by shift value.
# The position of a letter is the slot where that block sits in the encrypted data,
# e.g. shift 3 = "ACDB" means block B is stored in the 4th slot.
BLOCK_ORDER = [
    "ABCD", "ABDC", "ACBD", "ACDB", "ADBC", "ADCB",
    "BACD", "BADC", "BCAD", "BCDA", "BDAC", "BDCA",
    "CABD", "CADB", "CBAD", "CBDA", "CDAB", "CDBA",
    "DABC", "DACB", "DBAC", "DBCA", "DCAB", "DCBA",
]

STAT_NAMES = ["HP", "Atk", "Def", "Spe", "SpA", "SpD"]  # in-memory order
HP_TYPES = ["Fighting", "Flying", "Poison", "Ground", "Rock", "Bug", "Ghost", "Steel",
            "Fire", "Water", "Grass", "Electric", "Psychic", "Ice", "Dragon", "Dark"]


# ---------------------------------------------------------------- crypto

def _prng(seed: int):
    """Gen 4 LCRNG: yields the upper 16 bits of each successive state."""
    while True:
        seed = (0x41C64E6D * seed + 0x6073) & 0xFFFFFFFF
        yield seed >> 16


def _xor_words(data: bytes, seed: int) -> bytes:
    rng = _prng(seed)
    words = struct.unpack(f"<{len(data) // 2}H", data)
    return struct.pack(f"<{len(words)}H", *(w ^ next(rng) for w in words))


def shift_value(pid: int) -> int:
    return ((pid & 0x3E000) >> 0xD) % 24


def checksum(block_data: bytes) -> int:
    """Sum of the 64 decrypted words from 0x08-0x87, truncated to 16 bits."""
    return sum(struct.unpack("<64H", block_data)) & 0xFFFF


def decrypt(raw: bytes) -> bytes:
    """Encrypted 136/236-byte Pokémon -> decrypted, unshuffled bytes (same length)."""
    pid, _, chk = struct.unpack_from("<IHH", raw, 0)
    shuffled = _xor_words(raw[8:STORED_SIZE], chk)
    order = BLOCK_ORDER[shift_value(pid)]
    blocks = b"".join(
        shuffled[order.index(letter) * BLOCK_SIZE:(order.index(letter) + 1) * BLOCK_SIZE]
        for letter in "ABCD"
    )
    out = raw[:8] + blocks
    if len(raw) >= PARTY_SIZE:
        out += _xor_words(raw[STORED_SIZE:PARTY_SIZE], pid)
    return out


def encrypt(plain: bytes) -> bytes:
    """Inverse of decrypt(); handy for tests and for building sample data."""
    pid, _, chk = struct.unpack_from("<IHH", plain, 0)
    order = BLOCK_ORDER[shift_value(pid)]
    by_letter = {l: plain[8 + i * BLOCK_SIZE: 8 + (i + 1) * BLOCK_SIZE] for i, l in enumerate("ABCD")}
    shuffled = b"".join(by_letter[l] for l in order)
    out = plain[:8] + _xor_words(shuffled, chk)
    if len(plain) >= PARTY_SIZE:
        out += _xor_words(plain[STORED_SIZE:PARTY_SIZE], pid)
    return out


# ---------------------------------------------------------------- parsed model

@dataclass
class Pokemon:
    pid: int
    species_id: int
    species: str
    held_item: int
    tid: int
    sid: int
    exp: int
    friendship: int
    ability: str
    evs: dict
    ivs: dict
    moves: list            # [(name, pp), ...]
    move_ids: list         # in-game move IDs, same order as moves (look up with gamedata.move)
    is_egg: bool
    nature: str
    shiny: bool
    gender: str
    hidden_power: tuple    # (type, power)
    pokerus: int
    form: int = 0                  # alternate form index (Unown letter, Rotom form, ...)
    met_location: int = 0          # in-game location ID where it was caught/received
    met_level: int = 0             # 0 for Pokémon hatched from eggs
    met_date: tuple | None = None  # (year, month, day)
    egg_location: int = 0
    ball: int = 0                  # item ID of the Poké Ball
    held_item_name: str | None = None
    # party / battle section (None for 136-byte box data)
    level: int | None = None
    status: str | None = None
    hp: int | None = None
    max_hp: int | None = None
    stats: dict = field(default_factory=dict)
    in_battle: bool = False   # True when HP/status come from the live in-battle copy
    preview: bool = False     # True for a made-up Pokémon (picked in the calculator, not in the game)


def ivs_from_word(iv_word: int) -> dict:
    """The packed 32-bit IV value -> {"HP": .., "Atk": .., ...} (5 bits each, memory order)."""
    return {s: (iv_word >> (5 * i)) & 31 for i, s in enumerate(STAT_NAMES)}


def hidden_power_of(ivs: dict) -> tuple:
    """(type, power) of Hidden Power for these IVs (Gen 3-5 formula, power 30-70)."""
    # bit order HP, Atk, Def, Spe, SpA, SpD (same as memory order)
    t = sum((ivs[s] & 1) << i for i, s in enumerate(STAT_NAMES))
    p = sum(((ivs[s] >> 1) & 1) << i for i, s in enumerate(STAT_NAMES))
    return HP_TYPES[t * 15 // 63], p * 40 // 63 + 30


def _status_text(b: int) -> str:
    if b & 0x07:
        return f"Asleep ({b & 0x07})"
    for bit, name in ((0x80, "Toxic"), (0x08, "Poisoned"), (0x10, "Burned"),
                      (0x20, "Frozen"), (0x40, "Paralyzed")):
        if b & bit:
            return name
    return "OK"


def parse(raw: bytes, already_decrypted: bool = False) -> Pokemon | None:
    """Decode one Pokémon. Returns None for empty slots or bad data (checksum mismatch)."""
    if len(raw) not in (STORED_SIZE, PARTY_SIZE):
        return None
    pid, _, chk = struct.unpack_from("<IHH", raw, 0)
    if pid == 0 and chk == 0:
        return None  # empty slot

    d = raw if already_decrypted else decrypt(raw)
    if checksum(d[8:STORED_SIZE]) != chk:
        return None  # wrong address, stale memory, or caught mid-write

    species_id, item, tid, sid = struct.unpack_from("<HHHH", d, 0x08)
    if not 1 <= species_id <= 493:
        return None
    exp = struct.unpack_from("<I", d, 0x10)[0]
    evs = dict(zip(STAT_NAMES, d[0x18:0x1E]))

    move_ids = struct.unpack_from("<4H", d, 0x28)
    pps = d[0x30:0x34]
    moves = [(move_name(m), pp) for m, pp in zip(move_ids, pps) if m]

    iv_word = struct.unpack_from("<I", d, 0x38)[0]
    ivs = ivs_from_word(iv_word)

    flags = d[0x40]
    gender = "—" if flags & 0x04 else ("F" if flags & 0x02 else "M")

    shiny = (tid ^ sid ^ (pid >> 16) ^ (pid & 0xFFFF)) < 8

    hidden_power = hidden_power_of(ivs)

    # Platinum/HGSS store egg/met locations at 0x44/0x46; Diamond/Pearl used 0x7E/0x80.
    # Same fallback PKHeX uses: take the newer field when it's set.
    egg_new, met_new = struct.unpack_from("<HH", d, 0x44)
    egg_old, met_old = struct.unpack_from("<HH", d, 0x7E)
    egg_loc, met_loc = egg_new or egg_old, met_new or met_old
    year, month, day = d[0x7B:0x7E]

    mon = Pokemon(
        pid=pid, species_id=species_id, species=species_name(species_id),
        held_item=item, tid=tid, sid=sid, exp=exp, friendship=d[0x14],
        ability=ability_name(d[0x15]), evs=evs, ivs=ivs, moves=moves,
        move_ids=[m for m in move_ids if m],
        is_egg=bool(iv_word & (1 << 30)), nature=NATURES[pid % 25], shiny=shiny,
        gender=gender, hidden_power=hidden_power, pokerus=d[0x82],
        form=flags >> 3, met_location=met_loc, met_level=d[0x84] & 0x7F,
        met_date=(2000 + year, month, day) if month else None, egg_location=egg_loc,
        ball=max(d[0x86], d[0x83]),   # HGSS ball field vs older one; PKHeX shows the higher
        held_item_name=item_name(item),
    )

    if len(d) >= PARTY_SIZE:
        mon.status = _status_text(d[0x88])
        mon.level = d[0x8C]
        mon.hp, mon.max_hp, atk, df, spe, spa, spd = struct.unpack_from("<7H", d, 0x8E)
        mon.stats = {"HP": mon.max_hp, "Atk": atk, "Def": df, "Spe": spe, "SpA": spa, "SpD": spd}
    return mon


# ---------------------------------------------------------------- dump file

class IncompleteDump(Exception):
    """The dump file was read while tracker.lua was still writing it. Just retry."""


def read_dump(path: str) -> dict:
    """Parse the text file written by tracker.lua.

    Returns {"meta": {...}, "party": [Pokemon|None x6], "enemy": [Pokemon|None x6]}.
    Raises IncompleteDump if the file was caught mid-write (tracker.lua writes it in place).
    """
    with open(path, "r", encoding="ascii", errors="replace") as f:
        lines = f.read().split("\n")

    slot_lines = [l for l in lines if l[:1] in ("P", "E") and l[1:2].isdigit()]
    if len(slot_lines) != 12 or any(len(l) != 3 + 2 * PARTY_SIZE for l in slot_lines):
        raise IncompleteDump(path)

    meta, party, enemy = {}, [None] * 6, [None] * 6
    for line in lines:
        key, _, val = line.strip().partition("=")
        if not key:
            continue
        if key in [l[:2] for l in slot_lines]:
            slot = int(key[1:]) - 1
            try:
                mon = parse(bytes.fromhex(val))
            except ValueError:
                mon = None
            (party if key[0] == "P" else enemy)[slot] = mon
        else:
            meta[key] = val
    return {"meta": meta, "party": party, "enemy": enemy}
