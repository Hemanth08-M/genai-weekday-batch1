"""CSV-backed resource store. Seed CSVs are copied to data/state and only the tools mutate them."""
import csv
import shutil
import threading
from copy import deepcopy
from pathlib import Path

from .config import SEED_DIR, STATE_DIR

SCHEMAS = {
    "patients": ["patient_id", "name", "age", "condition", "specialty_needed", "status",
                 "priority", "doctor_id", "bed_id", "discharge_ready"],
    "doctors": ["doctor_id", "name", "specialty", "status", "current_patient_count",
                "shift_end", "current_patient_ids"],
    "beds": ["bed_id", "ward", "status", "patient_id"],
    "staff": ["staff_id", "name", "role", "capability", "status", "assigned_to"],
}
KEYS = {"patients": "patient_id", "doctors": "doctor_id", "beds": "bed_id", "staff": "staff_id"}


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return [{k: (v or "").strip() for k, v in row.items() if k} for row in csv.DictReader(f)]


def write_csv(path, columns, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


class HospitalStore:
    def __init__(self, seed_dir=SEED_DIR, state_dir=STATE_DIR):
        self.seed_dir = Path(seed_dir)
        self.state_dir = Path(state_dir)
        self.lock = threading.RLock()
        self.tables = {}
        self._reserved = set()
        self.load()

    def _path(self, name):
        return self.state_dir / f"{name}.csv"

    def load(self):
        with self.lock:
            self.state_dir.mkdir(parents=True, exist_ok=True)
            for name in SCHEMAS:
                if not self._path(name).exists():
                    shutil.copy(self.seed_dir / f"{name}.csv", self._path(name))
                self.tables[name] = read_csv(self._path(name))

    def reset(self):
        """Restore all four lists from the seed CSVs."""
        with self.lock:
            for name in SCHEMAS:
                shutil.copy(self.seed_dir / f"{name}.csv", self._path(name))
            self._reserved.clear()
            self.load()

    def save(self, name):
        write_csv(self._path(name), SCHEMAS[name], self.tables[name])

    def all(self, name):
        with self.lock:
            return deepcopy(self.tables[name])

    def _row(self, name, key_value):
        key = KEYS[name]
        return next((r for r in self.tables[name] if r[key] == key_value), None)

    def get(self, name, key_value):
        with self.lock:
            row = self._row(name, key_value)
            return deepcopy(row) if row else None

    def update(self, name, key_value, **changes):
        with self.lock:
            row = self._row(name, key_value)
            if row is None:
                return None
            row.update({k: "" if v is None else str(v) for k, v in changes.items()})
            self.save(name)
            return deepcopy(row)

    def insert(self, name, row):
        with self.lock:
            clean = {col: "" if row.get(col) is None else str(row.get(col)) for col in SCHEMAS[name]}
            self.tables[name].append(clean)
            self._reserved.discard(clean[KEYS[name]])
            self.save(name)
            return deepcopy(clean)

    def reserve_patient_id(self):
        """Hand out the next free patient id (the orchestrator reserves it before agents run in parallel)."""
        with self.lock:
            taken = {p["patient_id"] for p in self.tables["patients"]} | self._reserved
            numbers = [int(pid[1:]) for pid in taken if pid[1:].isdigit()]
            pid = f"P{(max(numbers) + 1 if numbers else 1):03d}"
            self._reserved.add(pid)
            return pid


_store = None
_store_lock = threading.Lock()


def get_store():
    global _store
    with _store_lock:
        if _store is None:
            _store = HospitalStore()
        return _store
