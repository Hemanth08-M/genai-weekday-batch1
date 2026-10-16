"""Current shift report: live CSVs of patients, doctors, beds, staff + logs; archive and start a new shift."""
import io
import zipfile
from datetime import datetime

import pandas as pd

from ..config import REPORTS_DIR
from ..store import SCHEMAS, get_store
from .shift_log import LOGS, get_shift_log

RESOURCE_TABLES = ("patients", "doctors", "beds", "staff")


def current_tables():
    store, log = get_store(), get_shift_log()
    tables = {name: pd.DataFrame(store.all(name), columns=SCHEMAS[name]) for name in RESOURCE_TABLES}
    for name, cols in LOGS.items():
        tables[name] = pd.DataFrame(log.read(name), columns=cols)
    return tables


def csv_bytes(df):
    return df.to_csv(index=False).encode("utf-8")


def zip_bytes(tables, summary_md):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, df in tables.items():
            zf.writestr(f"{name}.csv", df.to_csv(index=False))
        zf.writestr("shift_summary.md", summary_md)
    return buffer.getvalue()


def metrics(tables):
    p, d, b, s = (tables[n] for n in RESOURCE_TABLES)
    return {
        "Waiting patients": int((p["status"] == "waiting").sum()),
        "Admitted patients": int((p["status"] == "admitted").sum()),
        "Available doctors": int((d["status"] == "available").sum()),
        "Free beds": int((b["status"] == "free").sum()),
        "Available staff": int((s["status"] == "available").sum()),
    }


def summarize_shift(tables):
    log = get_shift_log()
    req = tables["request_log"]
    lines = [f"# Shift {log.shift_id} report", f"Started: {log.meta['started_at']}  ",
             f"Generated: {datetime.now().isoformat(timespec='seconds')}", "", "## Resource snapshot"]
    lines += [f"- {k}: {v}" for k, v in metrics(tables).items()]
    for status in ("assigned", "queued", "escalated", "completed", "retried"):
        part = req[req["status"] == status]
        lines += ["", f"## {status.title()} ({len(part)})"]
        lines += [f"- {r.request_id} ({r.type}, {r.priority}): {r.reason}" for r in part.itertuples()] or ["- none"]
    free = tables["beds"][tables["beds"]["status"] == "free"]
    lines += ["", "## Free beds by ward"]
    lines += [f"- {ward}: {len(g)}" for ward, g in free.groupby("ward")] or ["- none"]
    return "\n".join(lines)


def end_shift():
    """Archive the current shift report to reports/ and start a fresh shift (resources carry over)."""
    tables = current_tables()
    summary = summarize_shift(tables)
    log = get_shift_log()
    base = f"shift_{log.shift_id:03d}_{datetime.now():%Y%m%d-%H%M%S}"
    folder, n = REPORTS_DIR / base, 2
    while folder.exists():
        folder, n = REPORTS_DIR / f"{base}_{n}", n + 1
    folder.mkdir(parents=True)
    for name, df in tables.items():
        df.to_csv(folder / f"{name}.csv", index=False)
    (folder / "shift_summary.md").write_text(summary, encoding="utf-8")
    log.start_new_shift()
    return folder
