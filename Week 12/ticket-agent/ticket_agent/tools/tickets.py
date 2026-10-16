"""The five ticket tools. All state lives in Postgres - the LLM never 'remembers' a status, it looks it up.

When the agent calls these, Langfuse records each call with its arguments and result
(via the LangChain CallbackHandler), so there is nothing to instrument here.
"""
import json
from typing import Literal

from langchain_core.tools import tool

from ..db import connect

Status = Literal["open", "in_progress", "blocked", "done"]
Priority = Literal["low", "medium", "high"]


def _log(conn, ticket_id: int, event: str) -> None:
    conn.execute("INSERT INTO ticket_log (ticket_id, event) VALUES (%s, %s)", (ticket_id, event))


@tool
def create_ticket(title: str, description: str = "", priority: Priority = "medium") -> str:
    """Create a new ticket for a task assigned to the user. Returns the new ticket id."""
    with connect() as conn:
        row = conn.execute(
            "INSERT INTO tickets (title, description, priority) VALUES (%s, %s, %s) RETURNING id",
            (title, description, priority),
        ).fetchone()
        _log(conn, row["id"], f"created (priority={priority})")
    return f"Created ticket #{row['id']}: {title}"


@tool
def list_tickets(status: str = "") -> str:
    """List tickets. Pass a status (open, in_progress, blocked, done) to filter; empty returns all."""
    with connect() as conn:
        if status:
            rows = conn.execute(
                "SELECT id, title, status, priority FROM tickets WHERE status = %s ORDER BY id", (status,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT id, title, status, priority FROM tickets ORDER BY id").fetchall()
    return json.dumps(rows, default=str) if rows else "No tickets found."


@tool
def update_ticket_status(ticket_id: int, status: Status) -> str:
    """Change the status of a ticket."""
    with connect() as conn:
        row = conn.execute(
            "UPDATE tickets SET status = %s, updated_at = now() WHERE id = %s RETURNING title",
            (status, ticket_id),
        ).fetchone()
        if not row:
            return f"Ticket #{ticket_id} does not exist."
        _log(conn, ticket_id, f"status -> {status}")
    return f"Ticket #{ticket_id} ('{row['title']}') is now {status}."


@tool
def add_ticket_note(ticket_id: int, note: str) -> str:
    """Add a progress note to a ticket's log."""
    with connect() as conn:
        if not conn.execute("SELECT 1 FROM tickets WHERE id = %s", (ticket_id,)).fetchone():
            return f"Ticket #{ticket_id} does not exist."
        _log(conn, ticket_id, f"note: {note}")
    return f"Note added to ticket #{ticket_id}."


@tool
def get_ticket_history(ticket_id: int) -> str:
    """Show a ticket's details and its full event log."""
    with connect() as conn:
        ticket = conn.execute("SELECT * FROM tickets WHERE id = %s", (ticket_id,)).fetchone()
        if not ticket:
            return f"Ticket #{ticket_id} does not exist."
        log = conn.execute(
            "SELECT event, created_at FROM ticket_log WHERE ticket_id = %s ORDER BY id", (ticket_id,)
        ).fetchall()
    return json.dumps({"ticket": ticket, "log": log}, default=str)


TICKET_TOOLS = [create_ticket, list_tickets, update_ticket_status, add_ticket_note, get_ticket_history]
