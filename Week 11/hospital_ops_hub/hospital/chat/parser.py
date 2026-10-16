"""Turn chat text or CSV files into request rows."""
import csv
import io
import re
from datetime import timedelta

from ..orchestrator.intake import FIELDS

ROW_PATTERN = re.compile(r"^\s*[A-Z]{1,3}\d+[\w-]*\s*,")


def parse_csv_text(text):
    """Rows from CSV text (with or without the header line)."""
    lines = [ln for ln in text.strip().splitlines() if ln.strip()]
    if not lines:
        return []
    if not lines[0].lower().startswith("request_id"):
        lines.insert(0, ",".join(FIELDS))
    return [dict(r) for r in csv.DictReader(io.StringIO("\n".join(lines)))]


def parse_chat_message(text, clock, next_index):
    """A message may be pasted CSV rows (R02,2026-...,"...") or plain scenarios, one per line.
    Plain scenarios are stamped with the simulation clock, one minute apart."""
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    if lines and (lines[0].lower().startswith("request_id") or all(ROW_PATTERN.match(ln) for ln in lines)):
        return parse_csv_text(text)
    rows = []
    for i, line in enumerate(lines):
        rows.append({"request_id": f"C{next_index + i:03d}",
                     "timestamp": (clock + timedelta(minutes=i)).isoformat(timespec="minutes"),
                     "description": line, "location": "", "reported_by": "chat"})
    return rows


def unique_ids(rows, existing):
    """Avoid clashing with ids already logged this shift (e.g. running a batch twice)."""
    taken = set(existing)
    for row in rows:
        base = row.get("request_id") or "REQ"
        rid, n = base, 2
        while rid in taken:
            rid = f"{base}-{n}"
            n += 1
        row["request_id"] = rid
        taken.add(rid)
    return rows
