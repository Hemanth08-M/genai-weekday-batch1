"""Small time and trace helpers."""
from datetime import datetime


def parse_ts(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).strip())
    except ValueError:
        return None


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def trace_event(request_id, worker, event, detail=""):
    """One audit row: which request triggered which agent/worker and what it did."""
    return {"request_id": request_id, "worker": worker, "event": event,
            "detail": detail, "logged_at": now_iso()}
