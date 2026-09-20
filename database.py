"""
VidGrab Pro — Data Layer
SQLite based storage for users & download history.
"""

import os
import sqlite3
from contextlib import contextmanager
from werkzeug.security import generate_password_hash, check_password_hash

DB_NAME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vidgrab.db")


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                username   TEXT UNIQUE NOT NULL,
                email      TEXT UNIQUE NOT NULL,
                password   TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id       INTEGER NOT NULL,
                title         TEXT,
                url           TEXT,
                thumbnail     TEXT,
                platform      TEXT,
                media_type    TEXT,
                quality       TEXT,
                file_size     TEXT,
                created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        """)
    print("[db] ready")


# ---------- Users ----------

def create_user(username, email, password):
    try:
        with get_db() as conn:
            cur = conn.execute(
                "INSERT INTO users (username, email, password) VALUES (?,?,?)",
                (username, email, generate_password_hash(password)),
            )
            return {"ok": True, "id": cur.lastrowid}
    except sqlite3.IntegrityError:
        return {"ok": False, "error": "Username or email already taken"}


def verify_user(username, password):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ? OR email = ?",
            (username, username),
        ).fetchone()
    if row and check_password_hash(row["password"], password):
        return {"id": row["id"], "username": row["username"], "email": row["email"]}
    return None


def get_user(user_id):
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, username, email FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    return dict(row) if row else None


# ---------- History ----------

def add_history(user_id, **kw):
    with get_db() as conn:
        conn.execute("""
            INSERT INTO history (user_id, title, url, thumbnail, platform, media_type, quality, file_size)
            VALUES (?,?,?,?,?,?,?,?)
        """, (
            user_id,
            kw.get("title", "Unknown"),
            kw.get("url", ""),
            kw.get("thumbnail", ""),
            kw.get("platform", "unknown"),
            kw.get("media_type", "video"),
            kw.get("quality", "-"),
            kw.get("file_size", "-"),
        ))


def get_history(user_id, limit=100):
    with get_db() as conn:
        rows = conn.execute("""
            SELECT * FROM history WHERE user_id = ?
            ORDER BY created_at DESC LIMIT ?
        """, (user_id, limit)).fetchall()
    return [dict(r) for r in rows]


def delete_history(item_id, user_id):
    with get_db() as conn:
        conn.execute("DELETE FROM history WHERE id = ? AND user_id = ?", (item_id, user_id))


def clear_history(user_id):
    with get_db() as conn:
        conn.execute("DELETE FROM history WHERE user_id = ?", (user_id,))


def get_stats(user_id):
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) c FROM history WHERE user_id=?", (user_id,)).fetchone()["c"]
        video = conn.execute("SELECT COUNT(*) c FROM history WHERE user_id=? AND media_type='video'", (user_id,)).fetchone()["c"]
        audio = conn.execute("SELECT COUNT(*) c FROM history WHERE user_id=? AND media_type='audio'", (user_id,)).fetchone()["c"]
    return {"total": total, "video": video, "audio": audio}