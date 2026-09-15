"""
db.py
Lapisan persistensi: coba konek ke Supabase (PostgreSQL) lewat st.secrets/env var
SUPABASE_DB_URL, fallback otomatis ke SQLite lokal kalau gagal (offline, secret
belum diisi, dsb). Seluruh state aplikasi disimpan sebagai satu JSON blob (mengikuti
struktur dict DATA di app.py), plus tabel users & activity_log terpisah untuk
fitur login dan log aktivitas di sidebar.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets as pysecrets
import sqlite3
from datetime import datetime, timezone
from typing import Any, Optional

SQLITE_PATH = os.path.join(os.path.dirname(__file__), "local_data.db")

_cache: dict[str, Any] = {"conn": None, "dialect": None}


def _get_dsn() -> Optional[str]:
    try:
        import streamlit as st
        dsn = st.secrets.get("SUPABASE_DB_URL")
        if dsn:
            return dsn
    except Exception:
        pass
    return os.environ.get("SUPABASE_DB_URL")


def get_connection():
    """Return (conn, dialect). dialect: 'postgres' atau 'sqlite'.
    Di-cache per proses; dicek ulang liveness-nya setiap panggilan untuk koneksi postgres."""
    if _cache["conn"] is not None:
        if _cache["dialect"] == "postgres":
            try:
                cur = _cache["conn"].cursor()
                cur.execute("SELECT 1")
                cur.close()
                return _cache["conn"], _cache["dialect"]
            except Exception:
                _cache["conn"] = None
                _cache["dialect"] = None
        else:
            return _cache["conn"], _cache["dialect"]

    dsn = _get_dsn()
    if dsn:
        try:
            import psycopg2
            conn = psycopg2.connect(dsn, connect_timeout=5)
            conn.autocommit = True
            _init_schema(conn, "postgres")
            _cache["conn"], _cache["dialect"] = conn, "postgres"
            return conn, "postgres"
        except Exception:
            pass  # fallback ke SQLite di bawah

    conn = sqlite3.connect(SQLITE_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    _init_schema(conn, "sqlite")
    _cache["conn"], _cache["dialect"] = conn, "sqlite"
    return conn, "sqlite"


def _init_schema(conn, dialect: str) -> None:
    cur = conn.cursor()
    if dialect == "postgres":
        cur.execute("""
            CREATE TABLE IF NOT EXISTS app_state (
                id INTEGER PRIMARY KEY,
                data TEXT NOT NULL,
                updated_at TIMESTAMP NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS activity_log (
                id SERIAL PRIMARY KEY,
                ts TIMESTAMP NOT NULL,
                username TEXT NOT NULL,
                action TEXT NOT NULL
            )
        """)
    else:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS app_state (
                id INTEGER PRIMARY KEY,
                data TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                username TEXT NOT NULL,
                action TEXT NOT NULL
            )
        """)
        conn.commit()
    cur.close()


def _now():
    return datetime.now(timezone.utc)


def load_app_state() -> Optional[dict]:
    """Ambil state terakhir yang tersimpan. None kalau belum pernah disimpan."""
    conn, dialect = get_connection()
    ph = "%s" if dialect == "postgres" else "?"
    cur = conn.cursor()
    cur.execute(f"SELECT data FROM app_state WHERE id = {ph}", (1,))
    row = cur.fetchone()
    cur.close()
    if row:
        try:
            return json.loads(row[0])
        except Exception:
            return None
    return None


def save_app_state(data: dict) -> None:
    conn, dialect = get_connection()
    payload = json.dumps(data, default=str)
    now = _now()
    cur = conn.cursor()
    if dialect == "postgres":
        cur.execute(
            """
            INSERT INTO app_state (id, data, updated_at) VALUES (1, %s, %s)
            ON CONFLICT (id) DO UPDATE SET data = EXCLUDED.data, updated_at = EXCLUDED.updated_at
            """,
            (payload, now),
        )
    else:
        cur.execute(
            """
            INSERT INTO app_state (id, data, updated_at) VALUES (1, ?, ?)
            ON CONFLICT (id) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at
            """,
            (payload, now.isoformat()),
        )
        conn.commit()
    cur.close()


def log_action(username: str, action: str) -> None:
    conn, dialect = get_connection()
    now = _now()
    cur = conn.cursor()
    if dialect == "postgres":
        cur.execute("INSERT INTO activity_log (ts, username, action) VALUES (%s, %s, %s)",
                    (now, username, action))
    else:
        cur.execute("INSERT INTO activity_log (ts, username, action) VALUES (?, ?, ?)",
                    (now.isoformat(), username, action))
        conn.commit()
    cur.close()


def get_recent_logs(limit: int = 50) -> list[dict]:
    conn, dialect = get_connection()
    ph = "%s" if dialect == "postgres" else "?"
    cur = conn.cursor()
    cur.execute(f"SELECT ts, username, action FROM activity_log ORDER BY id DESC LIMIT {ph}", (limit,))
    rows = cur.fetchall()
    cur.close()
    return [{"Waktu": str(r[0]), "User": r[1], "Aksi": r[2]} for r in rows]


def _hash_password(password: str, salt: str) -> str:
    return hmac.new(salt.encode(), password.encode(), hashlib.sha256).hexdigest()


def create_user(username: str, password: str) -> tuple[bool, str]:
    conn, dialect = get_connection()
    salt = pysecrets.token_hex(16)
    pw_hash = _hash_password(password, salt)
    now = _now()
    cur = conn.cursor()
    try:
        if dialect == "postgres":
            cur.execute(
                "INSERT INTO users (username, password_hash, salt, created_at) VALUES (%s, %s, %s, %s)",
                (username, pw_hash, salt, now),
            )
        else:
            cur.execute(
                "INSERT INTO users (username, password_hash, salt, created_at) VALUES (?, ?, ?, ?)",
                (username, pw_hash, salt, now.isoformat()),
            )
            conn.commit()
        return True, "Registrasi berhasil."
    except Exception:
        return False, "Gagal registrasi — nama pengguna mungkin sudah dipakai."
    finally:
        cur.close()


def verify_user(username: str, password: str) -> bool:
    conn, dialect = get_connection()
    ph = "%s" if dialect == "postgres" else "?"
    cur = conn.cursor()
    cur.execute(f"SELECT password_hash, salt FROM users WHERE username = {ph}", (username,))
    row = cur.fetchone()
    cur.close()
    if not row:
        return False
    pw_hash, salt = row
    return hmac.compare_digest(_hash_password(password, salt), pw_hash)


def list_users() -> list[dict]:
    conn, _ = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT username, created_at FROM users ORDER BY id")
    rows = cur.fetchall()
    cur.close()
    return [{"Username": r[0], "Dibuat": str(r[1])} for r in rows]


def get_backend_label() -> str:
    _, dialect = get_connection()
    return "Supabase (PostgreSQL)" if dialect == "postgres" else "SQLite (lokal, fallback)"
