"""
Jarvis AI — Cost Tracker
========================
Tracks per-call API costs using token counts and known pricing.
"""

import logging
import sqlite3
import os
from datetime import datetime
from typing import Optional

logger = logging.getLogger("jarvis.cost")

DB_PATH = os.path.join(os.path.dirname(__file__), "costs.db")

# Price per token (input, output) in USD
PRICING: dict[str, tuple[float, float]] = {
    "gpt-4o":                            (5e-6,    15e-6),
    "gpt-4o-mini":                       (0.15e-6,  0.6e-6),
    "gpt-4-turbo":                       (10e-6,   30e-6),
    "claude-opus-4-5-20251001":          (15e-6,   75e-6),
    "claude-sonnet-4-5-20251001":        (3e-6,    15e-6),
    "claude-haiku-4-5-20251001":         (0.25e-6,  1.25e-6),
    "gemini-2.0-flash":                  (0.075e-6, 0.3e-6),
    "google/gemini-2.0-flash":           (0.075e-6, 0.3e-6),
    "mistral/mistral-7b-instruct":       (0.14e-6,  0.14e-6),
    "meta-llama/llama-3.1-70b-instruct": (0.81e-6,  0.81e-6),
    "anthropic/claude-3-haiku":          (0.25e-6,  1.25e-6),
    "anthropic/claude-3.5-sonnet":       (3e-6,    15e-6),
}


def _conn():
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.execute("""
        CREATE TABLE IF NOT EXISTS api_costs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT DEFAULT CURRENT_TIMESTAMP,
            model TEXT NOT NULL,
            session_id TEXT DEFAULT 'default',
            prompt_tokens INTEGER DEFAULT 0,
            completion_tokens INTEGER DEFAULT 0,
            cost_usd REAL DEFAULT 0
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_ts ON api_costs (ts)")
    c.commit()
    return c


def log_call(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    session_id: str = "default",
) -> float:
    rates = PRICING.get(model, (0.0, 0.0))
    cost = rates[0] * prompt_tokens + rates[1] * completion_tokens
    try:
        c = _conn()
        c.execute(
            "INSERT INTO api_costs (model, session_id, prompt_tokens, completion_tokens, cost_usd) VALUES (?,?,?,?,?)",
            (model, session_id, prompt_tokens, completion_tokens, cost),
        )
        c.commit()
        c.close()
    except Exception as exc:
        logger.error("Failed to log cost: %s", exc)
    return cost


def total_this_month() -> float:
    try:
        c = _conn()
        row = c.execute(
            "SELECT SUM(cost_usd) FROM api_costs WHERE ts >= date('now','start of month')"
        ).fetchone()
        c.close()
        return row[0] or 0.0
    except Exception:
        return 0.0


def summary() -> dict:
    try:
        c = _conn()
        rows = c.execute(
            "SELECT model, COUNT(*) as calls, SUM(prompt_tokens+completion_tokens) as tokens, SUM(cost_usd) as cost FROM api_costs GROUP BY model ORDER BY cost DESC"
        ).fetchall()
        c.close()
        return {
            "this_month_usd": total_this_month(),
            "by_model": [
                {"model": r[0], "calls": r[1], "total_tokens": r[2], "cost_usd": round(r[3], 6)}
                for r in rows
            ],
        }
    except Exception as exc:
        logger.error("Failed to get cost summary: %s", exc)
        return {}
