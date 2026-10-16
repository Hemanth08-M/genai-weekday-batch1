"""Work completion: release what a finished request was holding so queued work can move."""
from ..config import MAX_DOCTOR_LOAD
from ..reporting.shift_log import get_shift_log
from ..tools import run_tool
from ..utils import trace_event

WORKER = "Completion Handler"


def _release_staff(row):
    released = []
    for staff_id in [s for s in row["staff"].split("|") if s]:
        member = run_tool("list_staff", {})["staff"]
        current = next((s for s in member if s["staff_id"] == staff_id), None)
        if current and current["assigned_to"] == row["request_id"]:
            run_tool("release_staff", {"staff_id": staff_id})
            released.append(staff_id)
    return released


def _free_er_doctor(row):
    """An ER case is stabilised: the doctor goes back to available if their caseload allows."""
    if row["type"] != "er_emergency" or not row["doctor"]:
        return None
    doctor = run_tool("get_doctor", {"doctor_id": row["doctor"]})["doctor"]
    if doctor and doctor["status"] == "busy" and int(doctor["current_patient_count"] or 0) < MAX_DOCTOR_LOAD:
        run_tool("set_doctor_status", {"doctor_id": row["doctor"], "status": "available"})
        return row["doctor"]
    return None


def complete_requests(request_ids, clock_iso):
    """Mark requests completed and release their staff / ER doctor. Returns one result dict per id."""
    log = get_shift_log()
    rows = {r["request_id"].upper(): r for r in log.read("request_log")}
    results, trace = [], []
    for rid in dict.fromkeys(i.strip().upper() for i in request_ids if i.strip()):
        row = rows.get(rid)
        if row is None:
            results.append({"request_id": rid, "ok": False, "message": "not found in the current shift log"})
            continue
        if row["status"] in ("completed", "retried"):
            results.append({"request_id": row["request_id"], "ok": False, "message": f"already {row['status']}"})
            continue
        staff = _release_staff(row)
        doctor = _free_er_doctor(row)
        freed = [f"staff {', '.join(staff)}"] if staff else []
        freed += [f"doctor {doctor} back to available"] if doctor else []
        note = f"completed at {clock_iso}" + (f"; released {'; '.join(freed)}" if freed else "")
        log.update_request(row["request_id"], status="completed",
                           reason="; ".join(filter(None, [row["reason"], note])))
        trace.append(trace_event(row["request_id"], WORKER, "completed", note))
        results.append({"request_id": row["request_id"], "ok": True, "previous": row["status"],
                        "message": note, "released": staff + ([doctor] if doctor else [])})
    log.append("worker_trace", trace)
    return results


def queued_requests():
    """Queued rows in this shift that have not been completed or retried yet."""
    return [r for r in get_shift_log().read("request_log") if r["status"] == "queued"]
