"""Normalise raw request rows and flag malformed ones (never crash on bad input)."""
import re

from ..utils import parse_ts

FIELDS = ("request_id", "timestamp", "description", "location", "reported_by")


def normalize(raw_rows):
    rows, seen = [], set()
    for i, raw in enumerate(raw_rows or [], start=1):
        raw = raw if isinstance(raw, dict) else {}
        row = {f: str(raw.get(f) or "").strip() for f in FIELDS}
        row["retry_of"] = str(raw.get("retry_of") or "").strip()
        if not row["request_id"]:
            row["request_id"] = f"UNK{i:02d}"
        base, n = row["request_id"], 2
        while row["request_id"] in seen:
            row["request_id"] = f"{base}-{n}"
            n += 1
        seen.add(row["request_id"])
        rows.append(row)
    return rows


def validate(row):
    """Return a list of problems; empty list means the request is usable."""
    problems = []
    if not row["timestamp"]:
        problems.append("missing timestamp")
    elif parse_ts(row["timestamp"]) is None:
        problems.append(f"unreadable timestamp '{row['timestamp']}'")
    words = re.findall(r"[A-Za-z]{3,}", row["description"])
    if len(words) < 3:
        problems.append("description has no actionable details")
    return problems


def guess_priority(text):
    text = text.lower()
    if any(k in text for k in ("emergency", "unconscious", "seizure", "cardiac", "not breathing")):
        return "emergency"
    if "urgent" in text or "asap" in text:
        return "urgent"
    return "routine"
