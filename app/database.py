"""SQLite connection handling and schema."""
import os
import sqlite3
from contextlib import closing

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    email           TEXT NOT NULL UNIQUE,
    hashed_password TEXT NOT NULL,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    description TEXT,
    completed   INTEGER NOT NULL DEFAULT 0 CHECK (completed IN (0, 1)),
    owner_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tasks_owner ON tasks(owner_id, completed);
"""


def db_path() -> str:
    # Read at call time so tests can point this at a temp file.
    return os.getenv("DATABASE_PATH", "tasks.db")


def get_connection() -> sqlite3.Connection:
    # check_same_thread=False: FastAPI may run a dependency and its endpoint
    # in different worker threads. Each request still gets its own connection.
    conn = sqlite3.connect(db_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with closing(get_connection()) as conn:
        conn.executescript(SCHEMA)
        conn.commit()
