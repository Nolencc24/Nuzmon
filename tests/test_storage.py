"""Checks saved-data storage (SQLite) on a throwaway database. Run:  python tests/test_storage.py"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # project folder

from tracker import storage


def test():
    path = os.path.join(tempfile.mkdtemp(), "test.db")
    db = storage.connect(path)
    assert db.execute("PRAGMA user_version").fetchone()[0] == len(storage.MIGRATIONS)
    a = storage.current_run(db, "IPGE", 12345, 54321)
    assert storage.current_run(db, "IPGE", 12345, 54321) == a        # same save -> same run
    assert storage.current_run(db, "IPGE", 1, 2) != a                # different save -> new run
    db.close()
    db = storage.connect(path)                                        # reopening keeps data
    assert storage.current_run(db, "IPGE", 12345, 54321) == a
    db.close()
    print("All storage tests passed.")


if __name__ == "__main__":
    test()
