"""Postgres: connection, schema, and small helpers around the tickets table."""
import logging
import time

import psycopg
from psycopg.rows import dict_row

from .config import settings

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (
    id          SERIAL PRIMARY KEY,
    title       TEXT NOT NULL,
    description TEXT DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'open'
                CHECK (status IN ('open', 'in_progress', 'blocked', 'done')),
    priority    TEXT NOT NULL DEFAULT 'medium'
                CHECK (priority IN ('low', 'medium', 'high')),
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ticket_log (
    id         SERIAL PRIMARY KEY,
    ticket_id  INT REFERENCES tickets(id) ON DELETE CASCADE,
    event      TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);
"""

SEED = [
    ("Fix checkout timeout bug", "high", "in_progress"),
    ("Write refund API docs", "medium", "open"),
    ("Upgrade psycopg in payments service", "low", "open"),
]


def connect() -> psycopg.Connection:
    return psycopg.connect(settings.database_url, row_factory=dict_row, autocommit=True, connect_timeout=5)


def init_db(wait_seconds: int = 60) -> None:
    """Wait for Postgres to accept connections, then create the tables."""
    deadline = time.monotonic() + wait_seconds
    while True:
        try:
            with connect() as conn:
                conn.execute(SCHEMA)
            log.info("Postgres ready, tables in place")
            return
        except psycopg.OperationalError as exc:
            if time.monotonic() > deadline:
                raise RuntimeError(
                    "Postgres is not reachable. Start it with `docker compose up -d` "
                    f"and check `docker compose logs` ({exc})"
                ) from exc
            time.sleep(2)


def tickets_snapshot() -> str:
    """Compact view of all not-done tickets, injected into every prompt so the agent always sees live state."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, title, status, priority FROM tickets WHERE status <> 'done' ORDER BY id"
        ).fetchall()
    if not rows:
        return "(no active tickets)"
    return "\n".join(f"#{r['id']} [{r['status']}, {r['priority']}] {r['title']}" for r in rows)


def ping() -> None:
    """Raises if the database cannot be reached (used by the API health check)."""
    with connect() as conn:
        conn.execute("SELECT 1")


def fetch_tickets() -> list[dict]:
    with connect() as conn:
        return conn.execute("SELECT id, title, status, priority FROM tickets ORDER BY id").fetchall()


def print_tickets() -> None:
    rows = fetch_tickets()
    for r in rows:
        print(f"#{r['id']:<3} {r['status']:<12} {r['priority']:<7} {r['title']}")
    if not rows:
        print("(no tickets)")


def seed_tickets() -> None:
    """Reset the tickets to a known state. DESTRUCTIVE: truncates both tables."""
    with connect() as conn:
        conn.execute("TRUNCATE tickets, ticket_log RESTART IDENTITY")
        for title, priority, status in SEED:
            conn.execute(
                "INSERT INTO tickets (title, priority, status) VALUES (%s, %s, %s)", (title, priority, status)
            )


def wipe_tickets() -> None:
    with connect() as conn:
        conn.execute("TRUNCATE tickets, ticket_log RESTART IDENTITY")
