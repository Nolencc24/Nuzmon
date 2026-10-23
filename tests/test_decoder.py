"""Sanity checks for the decoder. Run from the project folder:  python tests/test_decoder.py

Uses two real Gen 4 Pokémon (from tracker/game/samples.py), encrypts them the way the
game stores party data, and checks they decode back exactly.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # project folder

from tracker.game.decoder import encrypt, parse
from tracker.game.samples import GEODUDE, SHINY_CUBONE, as_party


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
