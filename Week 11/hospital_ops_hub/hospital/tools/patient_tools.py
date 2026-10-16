"""Patient List Agent tools: add, look up, update status, list waiting."""
from typing import Optional

from langchain_core.tools import tool

from ..store import get_store

PATIENT_STATUSES = ("waiting", "admitted", "discharged")


@tool
def get_patient(patient_id: str) -> dict:
    """Fetch one patient record by id, e.g. P005."""
    row = get_store().get("patients", patient_id.strip().upper())
    return {"ok": row is not None, "patient": row,
            "error": None if row else f"Patient {patient_id} not found"}


@tool
def find_patient(query: str) -> dict:
    """Search patients by id or (partial) name, case-insensitive."""
    q = query.strip().lower()
    matches = [p for p in get_store().all("patients")
               if p["patient_id"].lower() == q or q in p["name"].lower()]
    return {"ok": True, "matches": matches}


@tool
def list_patients(status: Optional[str] = None) -> dict:
    """List patients, optionally filtered by status (waiting, admitted, discharged)."""
    rows = get_store().all("patients")
    if status:
        rows = [p for p in rows if p["status"] == status]
    return {"ok": True, "patients": rows}


@tool
def list_waiting_patients() -> dict:
    """List patients who are still waiting for care or a bed."""
    return {"ok": True, "patients": [p for p in get_store().all("patients") if p["status"] == "waiting"]}


@tool
def add_patient(patient_id: str, name: str, age: Optional[int] = None, condition: str = "",
                specialty_needed: str = "", priority: str = "routine", status: str = "waiting") -> dict:
    """Register a new patient in the patient list."""
    store = get_store()
    with store.lock:
        if store.get("patients", patient_id):
            return {"ok": False, "error": f"Patient {patient_id} already exists"}
        row = store.insert("patients", {
            "patient_id": patient_id, "name": name, "age": age or "", "condition": condition,
            "specialty_needed": specialty_needed, "status": status, "priority": priority,
            "doctor_id": "", "bed_id": "", "discharge_ready": "no"})
    return {"ok": True, "patient": row}


@tool
def update_patient_status(patient_id: str, status: str) -> dict:
    """Set a patient's status to waiting, admitted or discharged. Discharging clears the bed link."""
    if status not in PATIENT_STATUSES:
        return {"ok": False, "error": f"Invalid status '{status}'"}
    changes = {"status": status}
    if status == "discharged":
        changes.update(bed_id="", discharge_ready="no")
    row = get_store().update("patients", patient_id, **changes)
    return {"ok": row is not None, "patient": row,
            "error": None if row else f"Patient {patient_id} not found"}


@tool
def link_patient(patient_id: str, doctor_id: Optional[str] = None, bed_id: Optional[str] = None) -> dict:
    """Record the doctor and/or bed assigned to a patient. Linking a bed marks the patient admitted."""
    changes = {}
    if doctor_id is not None:
        changes["doctor_id"] = doctor_id
    if bed_id is not None:
        changes["bed_id"] = bed_id
        if bed_id:
            changes["status"] = "admitted"
    row = get_store().update("patients", patient_id, **changes)
    return {"ok": row is not None, "patient": row,
            "error": None if row else f"Patient {patient_id} not found"}


PATIENT_READ_TOOLS = [get_patient, find_patient, list_patients, list_waiting_patients]
PATIENT_TOOLS = PATIENT_READ_TOOLS + [add_patient, update_patient_status, link_patient]
