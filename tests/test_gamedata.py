"""Checks that the generated data has Gen 4 values (not modern ones). Run:  python tests/test_gamedata.py"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # project folder

from tracker.game import gamedata as gd


def test():
    # moves: IDs, Gen 4 power/accuracy, physical/special split
    assert len(gd.all_move_names()) == 467
    assert gd.move(85)["name"] == "Thunderbolt" and gd.move(85)["power"] == 95
    assert gd.move(237)["name"] == "Hidden Power"
    assert gd.move_by_name("tackle")["power"] == 35 and gd.move_by_name("tackle")["accuracy"] == 95
    assert gd.move_by_name("Crunch")["category"] == "Physical"
    assert gd.move_by_name("Fire Spin")["power"] == 15
    assert gd.move_by_name("Moonblast") is None                       # Gen 6 move

    # species: Gen 4 types and stats, forms in game order
    assert gd.species_name(152) == "Chikorita"
    assert gd.species(35)["types"] == ["Normal"]                      # no Fairy type
    assert gd.species(12)["base_stats"]["spa"] == 80                  # Butterfree before Gen 6
    assert gd.species(479, 2)["name"] == "Rotom-Wash"
    assert gd.species(479, 2)["types"] == ["Electric", "Ghost"]       # Ghost until Gen 5
    assert gd.species(493, 9)["types"] == ["???"] and gd.species(493, 10)["types"] == ["Fire"]
    assert gd.species(201, 26)["name"] == "Unown-Exclamation"

    # type chart: Steel resists Ghost and Dark in Gen 4
    assert gd.effectiveness("Ghost", ["Steel"]) == 0.5 and gd.effectiveness("Dark", ["Steel"]) == 0.5
    assert gd.effectiveness("Ground", ["Electric", "Flying"]) == 0
    assert gd.effectiveness("Fire", ["Grass", "Steel"]) == 4

    assert gd.ability_name(26) == "Levitate" and gd.item_name(234) == "Leftovers"
    print("All gamedata tests passed.")


if __name__ == "__main__":
    test()
