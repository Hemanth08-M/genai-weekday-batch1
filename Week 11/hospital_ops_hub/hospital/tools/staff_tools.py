"""Staff Agent tools: clerks, porters, cleaning teams, float pool; assign or release."""
from typing import Optional

from langchain_core.tools import tool

from ..store import get_store


def has_capability(member, capability):
    caps = member["capability"].split("|")
    return not capability or capability in caps or "any" in caps


@tool
def list_staff(role: Optional[str] = None, status: Optional[str] = None) -> dict:
    """List staff, optionally by role (clerk, porter, cleaning, float_pool, nurse) and status."""
    rows = get_store().all("staff")
    if role:
        rows = [s for s in rows if s["role"] == role]
    if status:
        rows = [s for s in rows if s["status"] == status]
    return {"ok": True, "staff": rows}


@tool
def list_available_staff(role: Optional[str] = None, capability: Optional[str] = None) -> dict:
    """Available staff matching a role and capability (e.g. porter + wheelchair, cleaning + biohazard)."""
    rows = list_staff.invoke({"role": role, "status": "available"})["staff"]
    return {"ok": True, "staff": [s for s in rows if has_capability(s, capability)]}


@tool
def assign_staff(staff_id: str, request_id: str) -> dict:
    """Assign an available (or on-call) staff member to a request."""
    store = get_store()
    with store.lock:
        member = store.get("staff", staff_id)
        if member is None:
            return {"ok": False, "error": f"Staff {staff_id} not found"}
        if member["status"] not in ("available", "on_call"):
            return {"ok": False, "error": f"Staff {staff_id} is {member['status']}"}
        row = store.update("staff", staff_id, status="busy", assigned_to=request_id)
    return {"ok": True, "staff": row}


@tool
def release_staff(staff_id: str) -> dict:
    """Release a staff member back to available."""
    row = get_store().update("staff", staff_id, status="available", assigned_to="")
    return {"ok": row is not None, "staff": row, "error": None if row else f"Staff {staff_id} not found"}


STAFF_READ_TOOLS = [list_staff, list_available_staff]
STAFF_TOOLS = STAFF_READ_TOOLS + [assign_staff, release_staff]
