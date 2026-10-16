"""Procedural memory: per-user working procedures ("how I want X handled") in Postgres.
Also holds the per-user PIN used to unlock a user's memory (see auth.py)."""
import json
import os
import time

from ..guardrails.injection import detect_injection

DEFAULT_URL = "postgresql://ticket_user:ticket_pass@localhost:5433/tickets"
SCHEMA = "hospital_ops"
MAX_USER_ID, MAX_NAME, MAX_STEPS, MAX_STEP_CHARS, MAX_PROCEDURES = 64, 60, 8, 200, 50
RETRY_AFTER_SEC = 30          # circuit breaker: skip Postgres this long after a failure
_ready = False
_down_until = 0.0


def _url():
    return os.getenv("DATABASE_URL", DEFAULT_URL)


def _connect():
    """Open a connection, or raise immediately while the circuit breaker is open."""
    global _down_until
    if time.time() < _down_until:
        raise ConnectionError("postgres circuit open")
    import psycopg
    try:
        return psycopg.connect(_url(), connect_timeout=2)
    except Exception:
        _down_until = time.time() + RETRY_AFTER_SEC
        raise


def reset_breaker():
    global _down_until, _ready
    _down_until, _ready = 0.0, False


def _ensure(conn):
    global _ready
    if _ready:
        return
    conn.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
    conn.execute(f"""CREATE TABLE IF NOT EXISTS {SCHEMA}.procedures (
        user_id TEXT NOT NULL, name TEXT NOT NULL, steps JSONB NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(), PRIMARY KEY (user_id, name))""")
    conn.execute(f"""CREATE TABLE IF NOT EXISTS {SCHEMA}.users (
        user_id TEXT PRIMARY KEY, salt BYTEA NOT NULL, pin_hash BYTEA NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now())""")
    conn.commit()
    _ready = True


def valid_user_id(user_id):
    return isinstance(user_id, str) and 0 < len(user_id.strip()) <= MAX_USER_ID


def clean_steps(name, steps):
    """Validate a procedure. Returns (name, steps) or raises ValueError."""
    name = " ".join(str(name).split()).lower()
    steps = [" ".join(str(s).split()) for s in steps if str(s).strip()]
    if not name or len(name) > MAX_NAME:
        raise ValueError("invalid procedure name")
    if not steps or len(steps) > MAX_STEPS or any(len(s) > MAX_STEP_CHARS for s in steps):
        raise ValueError("invalid procedure steps")
    if detect_injection(name + "\n" + "\n".join(steps)):
        raise ValueError("procedure looks like an injection")
    return name, steps


def upsert_procedure(user_id, name, steps):
    """Create or replace one named procedure (steps = list of strings). Returns True on success."""
    if not valid_user_id(user_id):
        return False
    try:
        name, steps = clean_steps(name, steps)
        with _connect() as conn:
            _ensure(conn)
            count = conn.execute(f"SELECT count(*) FROM {SCHEMA}.procedures WHERE user_id = %s",
                                 (user_id,)).fetchone()[0]
            exists = conn.execute(f"SELECT 1 FROM {SCHEMA}.procedures WHERE user_id = %s AND name = %s",
                                  (user_id, name)).fetchone()
            if count >= MAX_PROCEDURES and not exists:
                return False
            conn.execute(
                f"""INSERT INTO {SCHEMA}.procedures (user_id, name, steps) VALUES (%s, %s, %s)
                    ON CONFLICT (user_id, name) DO UPDATE SET steps = EXCLUDED.steps, updated_at = now()""",
                (user_id, name, json.dumps(steps)))
        return True
    except Exception:
        return False


def get_procedures(user_id):
    """Return {name: [steps]} for this user (empty if Postgres is unreachable)."""
    if not valid_user_id(user_id):
        return {}
    try:
        with _connect() as conn:
            _ensure(conn)
            rows = conn.execute(f"SELECT name, steps FROM {SCHEMA}.procedures WHERE user_id = %s "
                                "ORDER BY updated_at DESC", (user_id,)).fetchall()
        return {name: steps for name, steps in rows}
    except Exception:
        return {}


def delete_procedure(user_id, name):
    if not valid_user_id(user_id):
        return False
    try:
        with _connect() as conn:
            _ensure(conn)
            conn.execute(f"DELETE FROM {SCHEMA}.procedures WHERE user_id = %s AND name = %s",
                         (user_id, " ".join(str(name).split()).lower()))
        return True
    except Exception:
        return False


def delete_all_procedures(user_id):
    if not valid_user_id(user_id):
        return False
    try:
        with _connect() as conn:
            _ensure(conn)
            conn.execute(f"DELETE FROM {SCHEMA}.procedures WHERE user_id = %s", (user_id,))
        return True
    except Exception:
        return False
