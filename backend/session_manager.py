"""
Jarvis AI — Session Manager
============================
Manages multiple conversation sessions with metadata and cleanup.
"""

import json
import logging
import os
import sqlite3
from datetime import datetime
from typing import Optional, dict, Any

logger = logging.getLogger("jarvis.sessions")

DB_PATH = os.path.join(os.path.dirname(__file__), "sessions.db")


def init_sessions_db() -> None:
    """Initialize the sessions database."""
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_accessed TEXT DEFAULT CURRENT_TIMESTAMP,
                message_count INTEGER DEFAULT 0,
                metadata TEXT DEFAULT '{}'
            )
        """)
        conn.commit()
        conn.close()
        logger.info("Sessions database initialized.")
    except Exception as exc:
        logger.error("Failed to initialize sessions DB: %s", exc)


def create_session(session_id: str, name: str = None, metadata: dict = None) -> None:
    """Create a new named session."""
    if not name:
        name = f"Session {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.execute(
            """INSERT OR REPLACE INTO sessions (session_id, name, metadata)
               VALUES (?, ?, ?)""",
            (session_id, name, json.dumps(metadata or {})),
        )
        conn.commit()
        conn.close()
        logger.info("Created session: %s (%s)", session_id, name)
    except Exception as exc:
        logger.error("Failed to create session: %s", exc)


def get_sessions() -> list[dict[str, Any]]:
    """List all sessions with metadata."""
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT session_id, name, created_at, last_accessed, message_count FROM sessions ORDER BY last_accessed DESC"
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as exc:
        logger.error("Failed to get sessions: %s", exc)
        return []


def update_session_accessed(session_id: str) -> None:
    """Update last_accessed timestamp."""
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.execute(
            "UPDATE sessions SET last_accessed = CURRENT_TIMESTAMP WHERE session_id = ?",
            (session_id,),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def rename_session(session_id: str, new_name: str) -> None:
    """Rename a session."""
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.execute(
            "UPDATE sessions SET name = ? WHERE session_id = ?",
            (new_name, session_id),
        )
        conn.commit()
        conn.close()
        logger.info("Renamed session %s to '%s'", session_id, new_name)
    except Exception as exc:
        logger.error("Failed to rename session: %s", exc)


def delete_session_data(session_id: str) -> None:
    """Delete all data for a session (messages + session record)."""
    import database
    database.delete_session(session_id)

    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        conn.commit()
        conn.close()
        logger.info("Deleted session: %s", session_id)
    except Exception as exc:
        logger.error("Failed to delete session: %s", exc)


def cleanup_old_sessions(days: int = 30) -> int:
    """Delete sessions not accessed in N days. Returns count deleted."""
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        cursor = conn.execute(
            """SELECT session_id FROM sessions
               WHERE datetime(last_accessed) < datetime('now', '-' || ? || ' days')""",
            (days,),
        )
        old_ids = [row[0] for row in cursor.fetchall()]

        for sid in old_ids:
            delete_session_data(sid)

        conn.close()
        logger.info("Cleaned up %d old sessions (>%d days inactive)", len(old_ids), days)
        return len(old_ids)
    except Exception as exc:
        logger.error("Failed to cleanup sessions: %s", exc)
        return 0
