"""Sanity checks for decoder.py. Run:  python test_decoder.py

Uses two real Gen 4 Pokémon (decrypted .pk4 files from PKHeX's legality test set),
encrypts them the way the game stores party data, and checks they decode back exactly.
"""

import struct

from decoder import encrypt, parse

GEODUDE = bytes.fromhex(
    "44d7182300006eb14a000000a8a3f7893a010000464500020000000000000000000000000000000021006f00"
    "2c018d0123280f14000000006277743000000000020000000000d10031012f0139012e013f012e012f01ffff"
    "000000000000000700000000000000003c0153012d01ffff000000000000000000000013011c0000ba0b0001"
    "08040100")
SHINY_CUBONE = bytes.fromhex(
    "040000000000e4ab68000000b223b3234000000051450002000000000000000000000000000000002d002700"
    "00000000281e000000000000dd8360380000000002000000000012002d013f012c01390138012f01ffff0000"
    "000000000000000c00000000000000003a013a01530156014b01ffff0000000000000012050700001200000d"
    "04020000")


def as_party(stored: bytes, level: int, hp: int, max_hp: int) -> bytes:
    """Bolt a fake battle-stats section onto 136-byte box data -> 236 bytes."""
    battle = bytes([0x10, 0, 0, 0, level, 0]) + struct.pack("<7H", hp, max_hp, 11, 12, 13, 14, 15)
    return stored + battle + bytes(236 - 136 - len(battle))


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

    print("All decoder tests passed.")


if __name__ == "__main__":
    test()
