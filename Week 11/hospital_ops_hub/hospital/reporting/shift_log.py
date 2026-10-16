"""Per-shift request log, worker trace and escalations (CSV files in data/state)."""
import json
import threading
from pathlib import Path

from ..config import STATE_DIR
from ..models import ESCALATION_COLUMNS, LOG_COLUMNS, LOG_EXTRA_COLUMNS, TRACE_COLUMNS
from ..store import read_csv, write_csv
from ..utils import now_iso

LOGS = {
    "request_log": LOG_COLUMNS + LOG_EXTRA_COLUMNS,
    "worker_trace": TRACE_COLUMNS,
    "escalations": ESCALATION_COLUMNS,
}


class ShiftLog:
    def __init__(self, state_dir=STATE_DIR):
        self.state_dir = Path(state_dir)
        self.meta_path = self.state_dir / "shift.json"
        self.lock = threading.Lock()
        self.state_dir.mkdir(parents=True, exist_ok=True)
        if not self.meta_path.exists():
            self._start(1)

    def _start(self, shift_id):
        self.meta_path.write_text(json.dumps({"shift_id": shift_id, "started_at": now_iso()}), encoding="utf-8")
        for name, cols in LOGS.items():
            write_csv(self.state_dir / f"{name}.csv", cols, [])

    @property
    def meta(self):
        return json.loads(self.meta_path.read_text(encoding="utf-8"))

    @property
    def shift_id(self):
        return self.meta["shift_id"]

    def read(self, name):
        path = self.state_dir / f"{name}.csv"
        return read_csv(path) if path.exists() else []

    def append(self, name, rows):
        if not rows:
            return
        with self.lock:
            stamped = [{**r, "shift_id": self.shift_id} for r in rows]
            write_csv(self.state_dir / f"{name}.csv", LOGS[name], self.read(name) + stamped)

    def update_request(self, request_id, **changes):
        """Update one request_log row in place (completion, retry bookkeeping)."""
        with self.lock:
            rows = self.read("request_log")
            row = next((r for r in rows if r["request_id"] == request_id), None)
            if row is None:
                return None
            row.update({k: str(v) for k, v in changes.items()})
            write_csv(self.state_dir / "request_log.csv", LOGS["request_log"], rows)
            return row

    def existing_request_ids(self):
        return {r["request_id"] for r in self.read("request_log")}

    def start_new_shift(self):
        with self.lock:
            self._start(self.shift_id + 1)

    def reset(self):
        with self.lock:
            self._start(1)


_log = None


def get_shift_log():
    global _log
    if _log is None:
        _log = ShiftLog()
    return _log
