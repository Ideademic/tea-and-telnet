"""SQLite persistence layer for Tea & Telnet.

Everything runs in a single asyncio thread, so a plain synchronous sqlite3
connection is perfectly safe and keeps the code dependency-free.
"""

import hashlib
import os
import secrets
import sqlite3
import time

from . import config

_conn: sqlite3.Connection | None = None


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    username    TEXT UNIQUE NOT NULL COLLATE NOCASE,
    pw_hash     TEXT NOT NULL,
    pw_salt     TEXT NOT NULL,
    is_admin    INTEGER NOT NULL DEFAULT 0,
    created_at  INTEGER NOT NULL,
    last_seen   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_rooms (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name     TEXT NOT NULL,
    topic    TEXT NOT NULL DEFAULT '',
    position INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id    INTEGER NOT NULL,
    username   TEXT NOT NULL,
    body       TEXT NOT NULL,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS boards (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    position    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS posts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    board_id   INTEGER NOT NULL,
    number     INTEGER NOT NULL,
    username   TEXT NOT NULL,
    subject    TEXT NOT NULL,
    body       TEXT NOT NULL,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS read_pointers (
    user_id   INTEGER NOT NULL,
    board_id  INTEGER NOT NULL,
    last_read INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, board_id)
);
"""


def connect() -> sqlite3.Connection:
    """Open (once) the shared connection and ensure the schema + seed data."""
    global _conn
    if _conn is not None:
        return _conn

    path = config.DB_PATH
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)

    _conn = sqlite3.connect(path)
    _conn.row_factory = sqlite3.Row
    _conn.execute("PRAGMA journal_mode=WAL")
    _conn.execute("PRAGMA foreign_keys=ON")
    _conn.executescript(SCHEMA)
    _conn.commit()
    _seed()
    return _conn


def _seed() -> None:
    """Populate sensible defaults on a fresh database."""
    assert _conn is not None
    if get_setting("bbs_name") is None:
        set_setting("bbs_name", config.DEFAULT_BBS_NAME)

    if _conn.execute("SELECT COUNT(*) FROM chat_rooms").fetchone()[0] == 0:
        for i, (name, topic) in enumerate(
            [
                ("Lobby", "Pull up a chair and say hello"),
                ("Tech Talk", "Hardware, software, and everything between"),
                ("Late Night", "For the night owls"),
            ]
        ):
            _conn.execute(
                "INSERT INTO chat_rooms (name, topic, position) VALUES (?,?,?)",
                (name, topic, i),
            )

    if _conn.execute("SELECT COUNT(*) FROM boards").fetchone()[0] == 0:
        for i, (name, desc) in enumerate(
            [
                ("General", "General discussion and introductions"),
                ("Trade & Barter", "Buy, sell, swap"),
                ("The Archive", "Long-form posts and stories"),
            ]
        ):
            _conn.execute(
                "INSERT INTO boards (name, description, position) VALUES (?,?,?)",
                (name, desc, i),
            )
    _conn.commit()


# --------------------------------------------------------------------------- #
# Settings
# --------------------------------------------------------------------------- #
def get_setting(key: str) -> str | None:
    row = connect().execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else None


def set_setting(key: str, value: str) -> None:
    c = connect()
    c.execute(
        "INSERT INTO settings (key, value) VALUES (?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )
    c.commit()


def bbs_name() -> str:
    return get_setting("bbs_name") or config.DEFAULT_BBS_NAME


# --------------------------------------------------------------------------- #
# Users / auth
# --------------------------------------------------------------------------- #
def _hash_pw(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000
    ).hex()


def get_user(username: str) -> sqlite3.Row | None:
    return (
        connect()
        .execute("SELECT * FROM users WHERE username=?", (username,))
        .fetchone()
    )


def user_count() -> int:
    return connect().execute("SELECT COUNT(*) FROM users").fetchone()[0]


def create_user(username: str, password: str) -> sqlite3.Row:
    """Create a user. The very first account on the BBS becomes an admin."""
    c = connect()
    salt = secrets.token_hex(16)
    is_admin = 1 if user_count() == 0 else 0
    c.execute(
        "INSERT INTO users (username, pw_hash, pw_salt, is_admin, created_at, last_seen)"
        " VALUES (?,?,?,?,?,?)",
        (username, _hash_pw(password, salt), salt, is_admin, int(time.time()), int(time.time())),
    )
    c.commit()
    return get_user(username)


def verify_password(user: sqlite3.Row, password: str) -> bool:
    return secrets.compare_digest(_hash_pw(password, user["pw_salt"]), user["pw_hash"])


def set_password(user_id: int, password: str) -> None:
    c = connect()
    salt = secrets.token_hex(16)
    c.execute(
        "UPDATE users SET pw_hash=?, pw_salt=? WHERE id=?",
        (_hash_pw(password, salt), salt, user_id),
    )
    c.commit()


def touch_user(user_id: int) -> None:
    c = connect()
    c.execute("UPDATE users SET last_seen=? WHERE id=?", (int(time.time()), user_id))
    c.commit()


def list_users() -> list[sqlite3.Row]:
    return connect().execute("SELECT * FROM users ORDER BY username COLLATE NOCASE").fetchall()


def set_admin(user_id: int, is_admin: bool) -> None:
    c = connect()
    c.execute("UPDATE users SET is_admin=? WHERE id=?", (1 if is_admin else 0, user_id))
    c.commit()


# --------------------------------------------------------------------------- #
# Chat rooms
# --------------------------------------------------------------------------- #
def list_rooms() -> list[sqlite3.Row]:
    return connect().execute(
        "SELECT * FROM chat_rooms ORDER BY position, id"
    ).fetchall()


def get_room(room_id: int) -> sqlite3.Row | None:
    return connect().execute("SELECT * FROM chat_rooms WHERE id=?", (room_id,)).fetchone()


def add_room(name: str, topic: str = "") -> None:
    c = connect()
    pos = c.execute("SELECT COALESCE(MAX(position),0)+1 FROM chat_rooms").fetchone()[0]
    c.execute(
        "INSERT INTO chat_rooms (name, topic, position) VALUES (?,?,?)",
        (name, topic, pos),
    )
    c.commit()


def delete_room(room_id: int) -> None:
    c = connect()
    c.execute("DELETE FROM chat_rooms WHERE id=?", (room_id,))
    c.execute("DELETE FROM chat_messages WHERE room_id=?", (room_id,))
    c.commit()


def recent_messages(room_id: int, limit: int = 100) -> list[sqlite3.Row]:
    rows = connect().execute(
        "SELECT * FROM chat_messages WHERE room_id=? ORDER BY id DESC LIMIT ?",
        (room_id, limit),
    ).fetchall()
    return list(reversed(rows))


def add_message(room_id: int, username: str, body: str) -> sqlite3.Row:
    c = connect()
    now = int(time.time())
    cur = c.execute(
        "INSERT INTO chat_messages (room_id, username, body, created_at) VALUES (?,?,?,?)",
        (room_id, username, body, now),
    )
    # Trim history to keep the DB tidy.
    c.execute(
        "DELETE FROM chat_messages WHERE room_id=? AND id NOT IN "
        "(SELECT id FROM chat_messages WHERE room_id=? ORDER BY id DESC LIMIT ?)",
        (room_id, room_id, config.CHAT_HISTORY),
    )
    c.commit()
    return c.execute("SELECT * FROM chat_messages WHERE id=?", (cur.lastrowid,)).fetchone()


# --------------------------------------------------------------------------- #
# Boards (the "Tables") + posts + read pointers
# --------------------------------------------------------------------------- #
def list_boards() -> list[sqlite3.Row]:
    return connect().execute("SELECT * FROM boards ORDER BY position, id").fetchall()


def get_board(board_id: int) -> sqlite3.Row | None:
    return connect().execute("SELECT * FROM boards WHERE id=?", (board_id,)).fetchone()


def add_board(name: str, description: str = "") -> None:
    c = connect()
    pos = c.execute("SELECT COALESCE(MAX(position),0)+1 FROM boards").fetchone()[0]
    c.execute(
        "INSERT INTO boards (name, description, position) VALUES (?,?,?)",
        (name, description, pos),
    )
    c.commit()


def delete_board(board_id: int) -> None:
    c = connect()
    c.execute("DELETE FROM boards WHERE id=?", (board_id,))
    c.execute("DELETE FROM posts WHERE board_id=?", (board_id,))
    c.execute("DELETE FROM read_pointers WHERE board_id=?", (board_id,))
    c.commit()


def list_posts(board_id: int) -> list[sqlite3.Row]:
    return connect().execute(
        "SELECT * FROM posts WHERE board_id=? ORDER BY number", (board_id,)
    ).fetchall()


def get_post(board_id: int, number: int) -> sqlite3.Row | None:
    return connect().execute(
        "SELECT * FROM posts WHERE board_id=? AND number=?", (board_id, number)
    ).fetchone()


def post_count(board_id: int) -> int:
    return connect().execute(
        "SELECT COUNT(*) FROM posts WHERE board_id=?", (board_id,)
    ).fetchone()[0]


def add_post(board_id: int, username: str, subject: str, body: str) -> int:
    c = connect()
    number = c.execute(
        "SELECT COALESCE(MAX(number),0)+1 FROM posts WHERE board_id=?", (board_id,)
    ).fetchone()[0]
    c.execute(
        "INSERT INTO posts (board_id, number, username, subject, body, created_at)"
        " VALUES (?,?,?,?,?,?)",
        (board_id, number, username, subject, body, int(time.time())),
    )
    c.commit()
    return number


def get_read_pointer(user_id: int, board_id: int) -> int:
    row = connect().execute(
        "SELECT last_read FROM read_pointers WHERE user_id=? AND board_id=?",
        (user_id, board_id),
    ).fetchone()
    return row["last_read"] if row else 0


def set_read_pointer(user_id: int, board_id: int, last_read: int) -> None:
    c = connect()
    current = get_read_pointer(user_id, board_id)
    if last_read <= current:
        return
    c.execute(
        "INSERT INTO read_pointers (user_id, board_id, last_read) VALUES (?,?,?) "
        "ON CONFLICT(user_id, board_id) DO UPDATE SET last_read=excluded.last_read",
        (user_id, board_id, last_read),
    )
    c.commit()


def unread_count(user_id: int, board_id: int) -> int:
    last = get_read_pointer(user_id, board_id)
    return connect().execute(
        "SELECT COUNT(*) FROM posts WHERE board_id=? AND number>?", (board_id, last)
    ).fetchone()[0]
