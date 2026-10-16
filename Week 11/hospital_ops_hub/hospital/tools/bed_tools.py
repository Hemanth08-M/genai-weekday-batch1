"""Bed Manager Agent tools: free beds by ward (General, ICU, ER), assign, release."""
from typing import Optional

from langchain_core.tools import tool

from ..store import get_store


@tool
def list_beds(ward: Optional[str] = None, status: Optional[str] = None) -> dict:
    """List beds, optionally filtered by ward (General, ICU, ER) and status (free, occupied)."""
    rows = get_store().all("beds")
    if ward:
        rows = [b for b in rows if b["ward"].lower() == ward.lower()]
    if status:
        rows = [b for b in rows if b["status"] == status]
    return {"ok": True, "beds": rows}


@tool
def list_free_beds(ward: Optional[str] = None) -> dict:
    """List free beds, optionally in one ward (General, ICU, ER)."""
    return list_beds.invoke({"ward": ward, "status": "free"})


@tool
def list_discharge_ready_beds(ward: Optional[str] = None) -> dict:
    """Occupied beds whose patient is flagged discharge-ready (candidates to free up a full ward)."""
    store = get_store()
    patients = {p["patient_id"]: p for p in store.all("patients")}
    beds = []
    for bed in list_beds.invoke({"ward": ward, "status": "occupied"})["beds"]:
        patient = patients.get(bed["patient_id"])
        if patient and patient["discharge_ready"] == "yes":
            beds.append({**bed, "patient_name": patient["name"], "doctor_id": patient["doctor_id"]})
    return {"ok": True, "beds": beds}


@tool
def assign_bed(bed_id: str, patient_id: str) -> dict:
    """Put a patient in a free bed."""
    store = get_store()
    with store.lock:
        bed = store.get("beds", bed_id)
        if bed is None:
            return {"ok": False, "error": f"Bed {bed_id} not found"}
        if bed["status"] != "free":
            return {"ok": False, "error": f"Bed {bed_id} is occupied by {bed['patient_id']}"}
        row = store.update("beds", bed_id, status="occupied", patient_id=patient_id)
    return {"ok": True, "bed": row}


@tool
def release_bed(bed_id: str) -> dict:
    """Free a bed."""
    row = get_store().update("beds", bed_id, status="free", patient_id="")
    return {"ok": row is not None, "bed": row, "error": None if row else f"Bed {bed_id} not found"}


BED_READ_TOOLS = [list_beds, list_free_beds, list_discharge_ready_beds]
BED_TOOLS = BED_READ_TOOLS + [assign_bed, release_bed]
