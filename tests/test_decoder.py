"""Sanity checks for the decoder. Run from the project folder:  python tests/test_decoder.py

Uses two real Gen 4 Pokémon (from tracker/game/samples.py), encrypts them the way the
game stores party data, and checks they decode back exactly.
"""

import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # project folder

from tracker.game.decoder import (BOX_OPEN, PARTY_OPEN, PARTY_SIZE, STORED_SIZE, _xor_words, encrypt,
                                  parse)
from tracker.game.samples import GEODUDE, SHINY_CUBONE, as_party


def real_party(stored: bytes, level: int, hp: int) -> bytes:
    """Like as_party(), but with the stats the game itself would store (the stat formula)."""
    from tracker.game import gamedata
    from tracker.game.stats import calc_stats
    box = parse(stored, already_decrypted=True)               # the samples are stored decrypted
    s = calc_stats(gamedata.species(box.species_id, box.form)["base_stats"], box.ivs, box.evs, level,
                   box.nature, box.species_id)
    battle = bytes([0, 0, 0, 0, level, 0]) + struct.pack("<7H", hp, s["HP"], s["Atk"], s["Def"], s["Spe"],
                                                         s["SpA"], s["SpD"])
    return stored + battle + bytes(PARTY_SIZE - STORED_SIZE - len(battle))


def real_max_hp(plain: bytes) -> int:
    return struct.unpack_from("<H", plain, STORED_SIZE + 8)[0]


def test():
    g = parse(encrypt(as_party(GEODUDE, 12, 20, 33)))
    assert g is not None, "checksum failed"
    assert g.species == "Geodude" and g.nature == "Relaxed" and not g.shiny
    assert list(g.ivs.values()) == [2, 27, 29, 8, 7, 24]
    assert g.moves[0] == ("Tackle", 35)
    assert (g.level, g.hp, g.max_hp, g.status) == (12, 20, 33, "Burned")

    c = parse(encrypt(as_party(SHINY_CUBONE, 5, 19, 19)))
    assert c is not None and c.species == "Cubone" and c.shiny and c.nature == "Naughty"

    # corrupt one byte -> must be rejected rather than showing garbage
    bad = bytearray(encrypt(as_party(GEODUDE, 12, 20, 33)))
    bad[0x40] ^= 0xFF
    assert parse(bytes(bad)) is None

    # caught while the game is changing it (every step you walk): the game decrypts the
    # Pokémon in place and sets a flag at 0x04. Those sections must not be decrypted again.
    plain = as_party(GEODUDE, 12, 20, 33)
    enc = encrypt(plain)
    chk = struct.unpack_from("<H", enc, 6)[0]
    party_open = bytearray(enc)                               # level / HP / stats in plain text
    party_open[STORED_SIZE:PARTY_SIZE] = plain[STORED_SIZE:PARTY_SIZE]
    struct.pack_into("<H", party_open, 4, PARTY_OPEN)
    box_open = bytearray(enc)                                 # 4 blocks decrypted (still shuffled)
    box_open[8:STORED_SIZE] = _xor_words(enc[8:STORED_SIZE], chk)
    struct.pack_into("<H", box_open, 4, BOX_OPEN)
    both = bytearray(box_open)
    both[STORED_SIZE:PARTY_SIZE] = plain[STORED_SIZE:PARTY_SIZE]
    struct.pack_into("<H", both, 4, PARTY_OPEN | BOX_OPEN)
    for raw in (party_open, box_open, both):
        m = parse(bytes(raw))
        assert m is not None and (m.species, m.level, m.hp, m.max_hp, m.status) == ("Geodude", 12, 20, 33, "Burned")
        assert m.ivs == g.ivs and m.moves == g.moves

    # Reading the running game: the level / HP / stats section has no checksum, and the game
    # clears its "decrypted" flag *before* re-encrypting, so reads can catch it garbled.
    from tracker.game.sources import MemorySource, decode_live, plausible
    real = real_party(GEODUDE, 12, 20)                        # stats as the game would store them
    renc = encrypt(real)
    assert plausible(parse(renc)) and not plausible(parse(enc))   # the samples' made-up stats aren't
    assert decode_live(renc).level == 12
    flag_cleared = bytearray(renc)                            # flag cleared, section still plain text
    flag_cleared[STORED_SIZE:PARTY_SIZE] = real[STORED_SIZE:PARTY_SIZE]
    assert parse(bytes(flag_cleared)).level != 12             # the old way: garbage
    m = decode_live(bytes(flag_cleared))
    assert (m.level, m.hp, m.max_hp) == (12, 20, real_max_hp(real))
    half = bytearray(renc)                                    # re-encrypted part way through the stats:
    half[STORED_SIZE:STORED_SIZE + 12] = real[STORED_SIZE:STORED_SIZE + 12]   # garbage either way
    assert decode_live(bytes(half)) is None

    # a slot caught mid-update keeps its last good reading (same Pokémon only)
    src = MemorySource.__new__(MemorySource)                  # no DeSmuME needed for this part
    src.last_good = {"party": [None] * 6, "enemy": [None] * 6}
    src.previous = {"party": [None] * 6, "enemy": [None] * 6}
    empty = bytes(PARTY_SIZE)
    read = lambda first: src._read_team("party", [bytes(first)] + [empty] * 5)
    first = read(renc)
    assert first[0].level == 12 and first[1] is None
    assert read(half)[0].level == 12                          # garbled section: last good reading
    assert read(flag_cleared)[0].level == 12                  # decoded right, even with the flag off
    torn = bytearray(renc)
    torn[0x40] ^= 0xFF                                        # checksum doesn't match yet
    assert read(torn)[0].level == 12
    other_torn = bytearray(encrypt(as_party(SHINY_CUBONE, 5, 19, 19)))
    other_torn[0x40] ^= 0xFF                                  # a different Pokémon: no fallback
    assert read(other_torn)[0] is None
    assert read(empty)[0] is None                             # really emptied: shows empty
    odd = encrypt(as_party(GEODUDE, 12, 20, 33))              # passes the checksum, stats don't add up:
    assert read(odd)[0].hp == 20                              # a Pokémon we had no reading of: shown

    print("All decoder tests passed.")


if __name__ == "__main__":
    test()
