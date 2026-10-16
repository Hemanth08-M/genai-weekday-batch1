"""Doctor List Agent tools: specialty, availability, patient count, shift end, busy/free."""
from typing import Optional

from langchain_core.tools import tool

from ..config import MAX_DOCTOR_LOAD, SHIFT_END_BUFFER_MIN
from ..store import get_store
from ..utils import parse_ts


def _ids(doc):
    return [p for p in doc["current_patient_ids"].split("|") if p]


def check_eligibility(doc, specialty, at, is_er):
    """Apply availability + time rules. Returns (eligible, reason)."""
    if specialty and doc["specialty"] != specialty:
        return False, f"{doc['doctor_id']} is {doc['specialty']}"
    if doc["status"] != "available":
        return False, f"{doc['doctor_id']} is {doc['status']}"
    end = parse_ts(doc["shift_end"])
    if at and end:
        minutes_left = (end - at).total_seconds() / 60
        if minutes_left <= 0:
            return False, f"{doc['doctor_id']} shift already ended"
        if minutes_left < SHIFT_END_BUFFER_MIN and not is_er:
            return False, f"{doc['doctor_id']} shift ends in {minutes_left:.0f} min (<{SHIFT_END_BUFFER_MIN}, non-ER)"
    return True, "eligible"


def known_specialties():
    return sorted({d["specialty"] for d in get_store().all("doctors")})


@tool
def list_doctors(specialty: Optional[str] = None, available_only: bool = False) -> dict:
    """List doctors, optionally by specialty or only those marked available."""
    rows = get_store().all("doctors")
    if specialty:
        rows = [d for d in rows if d["specialty"] == specialty]
    if available_only:
        rows = [d for d in rows if d["status"] == "available"]
    return {"ok": True, "doctors": rows}


@tool
def get_doctor(doctor_id: str) -> dict:
    """Fetch one doctor record by id, e.g. D01."""
    row = get_store().get("doctors", doctor_id.strip().upper())
    return {"ok": row is not None, "doctor": row, "error": None if row else f"Doctor {doctor_id} not found"}


@tool
def find_eligible_doctors(specialty: Optional[str] = None, request_time: Optional[str] = None,
                          is_er: bool = False) -> dict:
    """Doctors who can take a patient now: available, right specialty, and not ending shift within
    30 minutes (the 30-minute rule is waived for ER cases). Sorted by lowest patient load."""
    at = parse_ts(request_time)
    eligible, rejected = [], []
    for doc in get_store().all("doctors"):
        ok, reason = check_eligibility(doc, specialty, at, is_er)
        if ok:
            eligible.append(doc)
        elif not specialty or doc["specialty"] == specialty:
            rejected.append({"doctor_id": doc["doctor_id"], "reason": reason})
    eligible.sort(key=lambda d: int(d["current_patient_count"] or 0))
    return {"ok": True, "eligible": eligible, "rejected": rejected}


@tool
def assign_doctor(doctor_id: str, patient_id: str, is_er: bool = False, override: bool = False) -> dict:
    """Assign a patient to a doctor. ER cases mark the doctor busy; otherwise busy at max load.
    override=True lets the Reallocation Worker pull a busy doctor for an ER case."""
    store = get_store()
    with store.lock:
        doc = store.get("doctors", doctor_id)
        if doc is None:
            return {"ok": False, "error": f"Doctor {doctor_id} not found"}
        if doc["status"] != "available" and not override:
            return {"ok": False, "error": f"Doctor {doctor_id} is {doc['status']}"}
        ids = _ids(doc)
        if patient_id not in ids:
            ids.append(patient_id)
        busy = is_er or len(ids) >= MAX_DOCTOR_LOAD
        row = store.update("doctors", doctor_id, current_patient_ids="|".join(ids),
                           current_patient_count=len(ids), status="busy" if busy else "available")
    return {"ok": True, "doctor": row}


@tool
def release_doctor(doctor_id: str, patient_id: str) -> dict:
    """Remove a patient from a doctor's list; a doctor with no patients becomes available."""
    store = get_store()
    with store.lock:
        doc = store.get("doctors", doctor_id)
        if doc is None:
            return {"ok": False, "error": f"Doctor {doctor_id} not found"}
        ids = [p for p in _ids(doc) if p != patient_id]
        status = "available" if not ids else doc["status"]
        row = store.update("doctors", doctor_id, current_patient_ids="|".join(ids),
                           current_patient_count=len(ids), status=status)
    return {"ok": True, "doctor": row}


@tool
def set_doctor_status(doctor_id: str, status: str) -> dict:
    """Mark a doctor busy or available."""
    if status not in ("available", "busy"):
        return {"ok": False, "error": f"Invalid status '{status}'"}
    row = get_store().update("doctors", doctor_id, status=status)
    return {"ok": row is not None, "doctor": row, "error": None if row else f"Doctor {doctor_id} not found"}


DOCTOR_READ_TOOLS = [list_doctors, get_doctor, find_eligible_doctors]
DOCTOR_TOOLS = DOCTOR_READ_TOOLS + [assign_doctor, release_doctor, set_doctor_status]
