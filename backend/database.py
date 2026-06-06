"""
Jarvis AI Assistant — Database & Memory Management
===================================================
Handles conversation persistence. Automatically connects to Supabase if configured;
otherwise falls back to a local SQLite database (jarvis.db) so it always works.
"""

import logging
import sqlite3
import os
from contextlib import contextmanager
from typing import Any
from config import config

logger = logging.getLogger("jarvis.database")

SQLITE_DB_PATH = os.path.join(os.path.dirname(__file__), "jarvis.db")

_supabase_client = None


@contextmanager
def _sqlite_conn():
    conn = sqlite3.connect(SQLITE_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_supabase_client():
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client
    if not config.supabase_url or not config.supabase_key:
        return None
    try:
        from supabase import create_client
        _supabase_client = create_client(config.supabase_url, config.supabase_key)
        return _supabase_client
    except Exception as exc:
        logger.error("Failed to initialize Supabase client: %s", exc)
        return None


def init_db() -> None:
    client = get_supabase_client()
    if client:
        logger.info("Supabase configured. Verifying memory table...")
        try:
            client.table("jarvis_memory").select("id").limit(1).execute()
            logger.info("Supabase memory table ready.")
        except Exception as exc:
            logger.warning("Cannot access 'jarvis_memory' table: %s", exc)
    else:
        logger.info("Initializing local SQLite database...")
        try:
            with _sqlite_conn() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS jarvis_memory (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        session_id TEXT DEFAULT 'default' NOT NULL
                    )
                """)
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_session ON jarvis_memory (session_id)"
                )
            logger.info("SQLite database ready.")
        except Exception as exc:
            logger.error("Failed to initialize SQLite database: %s", exc)


def save_message(role: str, content: Any, session_id: str = "default") -> None:
    if isinstance(content, list):
        content_str = "\n".join(p["text"] for p in content if p.get("type") == "text")
    else:
        content_str = str(content)[:50_000]  # cap at 50KB per message

    client = get_supabase_client()
    if client:
        try:
            client.table("jarvis_memory").insert(
                {"role": role, "content": content_str, "session_id": session_id}
            ).execute()
            return
        except Exception as exc:
            logger.error("Supabase save failed, falling back to SQLite: %s", exc)

    _save_sqlite(role, content_str, session_id)


def _save_sqlite(role: str, content_str: str, session_id: str) -> None:
    try:
        with _sqlite_conn() as conn:
            conn.execute(
                "INSERT INTO jarvis_memory (role, content, session_id) VALUES (?, ?, ?)",
                (role, content_str, session_id),
            )
    except Exception as exc:
        logger.error("Failed to save message to SQLite: %s", exc)


def load_messages(session_id: str = "default", limit: int = 50) -> list[dict[str, Any]]:
    client = get_supabase_client()
    if client:
        try:
            response = (
                client.table("jarvis_memory")
                .select("role, content")
                .eq("session_id", session_id)
                .order("created_at", desc=False)
                .limit(limit)
                .execute()
            )
            return [{"role": r["role"], "content": r["content"]} for r in response.data]
        except Exception as exc:
            logger.error("Supabase load failed: %s", exc)

    return _load_sqlite(session_id, limit)


def _load_sqlite(session_id: str, limit: int) -> list[dict[str, Any]]:
    try:
        with _sqlite_conn() as conn:
            rows = conn.execute(
                """SELECT role, content FROM (
                    SELECT role, content, id FROM jarvis_memory
                    WHERE session_id = ? ORDER BY id DESC LIMIT ?
                ) ORDER BY id ASC""",
                (session_id, limit),
            ).fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in rows]
    except Exception as exc:
        logger.error("Failed to load messages from SQLite: %s", exc)
        return []


def delete_session(session_id: str) -> None:
    client = get_supabase_client()
    if client:
        try:
            client.table("jarvis_memory").delete().eq("session_id", session_id).execute()
            return
        except Exception as exc:
            logger.error("Supabase delete failed: %s", exc)

    try:
        with _sqlite_conn() as conn:
            conn.execute("DELETE FROM jarvis_memory WHERE session_id = ?", (session_id,))
    except Exception as exc:
        logger.error("SQLite delete failed: %s", exc)
