"""
Saved user data (things you create, which must survive restarts): SQLite.

Reference data (moves, species...) is read-only JSON in tracker/data/. This module is for
data the app *writes*, like encounters per route later on. It lives in userdata/tracker.db
in the project folder (ignored by git).

Changing the schema: never edit a migration that has already shipped. Append a new SQL
string to MIGRATIONS instead; each database remembers how many it has applied
(PRAGMA user_version) and runs only the new ones on next start.

    from tracker import storage
    db = storage.connect()
    run_id = storage.current_run(db, game="IPGE", trainer_id=12345, secret_id=54321)
"""

from __future__ import annotations

import os
import sqlite3

DEFAULT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "userdata", "tracker.db")

MIGRATIONS = [
    # 1: a "run" is one playthrough (one save file). Everything recorded later
    #    (encounters, deaths, notes...) hangs off a run.
    """
    CREATE TABLE runs (
        id          INTEGER PRIMARY KEY,
        name        TEXT NOT NULL,
        game        TEXT NOT NULL,            -- game code, e.g. IPGE = SoulSilver (US)
        trainer_id  INTEGER,
        secret_id   INTEGER,
        created_at  TEXT NOT NULL DEFAULT (datetime('now')),
        archived    INTEGER NOT NULL DEFAULT 0
    );
    CREATE INDEX runs_by_trainer ON runs (game, trainer_id, secret_id);
    """,
]


def connect(path: str = DEFAULT_PATH) -> sqlite3.Connection:
    """Open (creating if needed) the database and bring its schema up to date."""
    if path != ":memory:":
        os.makedirs(os.path.dirname(path), exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    migrate(db)
    return db


def migrate(db: sqlite3.Connection) -> None:
    version = db.execute("PRAGMA user_version").fetchone()[0]
    for number, sql in enumerate(MIGRATIONS[version:], start=version + 1):
        with db:   # each migration is all-or-nothing
            db.executescript(sql)
            db.execute(f"PRAGMA user_version = {number}")


def current_run(db: sqlite3.Connection, game: str, trainer_id: int | None = None,
                secret_id: int | None = None, name: str | None = None) -> int:
    """ID of the active run for this save, creating one the first time it's seen."""
    row = db.execute(
        "SELECT id FROM runs WHERE game = ? AND trainer_id IS ? AND secret_id IS ? AND NOT archived "
        "ORDER BY id DESC LIMIT 1", (game, trainer_id, secret_id)).fetchone()
    if row:
        return row["id"]
    with db:
        cur = db.execute("INSERT INTO runs (name, game, trainer_id, secret_id) VALUES (?, ?, ?, ?)",
                         (name or f"{game} run", game, trainer_id, secret_id))
    return cur.lastrowid
