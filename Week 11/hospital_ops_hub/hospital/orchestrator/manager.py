"""Manager / Orchestrator node + the Send() router that spawns agents on demand."""
import time

from langgraph.types import Send

from ..config import PRIORITY_RANK
from ..store import get_store
from ..tools.doctor_tools import known_specialties
from ..tools.patient_tools import find_patient, get_patient
from ..utils import trace_event
from .intake import guess_priority, normalize, validate
from .playbook import AGENT_LABELS, plan_dispatch
from .triage import triage_rows

NEEDS_PATIENT_RECORD = {"new_patient", "er_emergency", "emergency_admission", "routine_bed"}


def _resolve_patient(request, tri):
    """Match an existing patient or reserve a new id, so parallel agents share one patient_ref."""
    if tri.patient_id:
        found = get_patient.invoke({"patient_id": tri.patient_id})
        if found["ok"]:
            return found["patient"]["patient_id"], found["patient"]["name"], False
    if tri.patient_name:
        exact = [p for p in find_patient.invoke({"query": tri.patient_name})["matches"]
                 if p["name"].lower() == tri.patient_name.lower() and p["status"] != "discharged"]
        if exact:
            return exact[0]["patient_id"], exact[0]["name"], False
    if request["type"] in NEEDS_PATIENT_RECORD:
        return get_store().reserve_patient_id(), tri.patient_name, True
    return None, tri.patient_name, False


def _sort_key(request):
    return (PRIORITY_RANK.get(request["priority"], 9), request["timestamp"] or "9999", request["request_id"])


def _new_outcome(request, started):
    return {"request_id": request["request_id"], "type": request["type"], "priority": request["priority"],
            "timestamp": request["timestamp"], "description": request["description"],
            "retry_of": request.get("retry_of", ""), "patient": "", "doctor": "", "bed": "",
            "staff": [], "notes": [], "queued": [], "unresolved": [], "workers": ["Orchestrator"],
            "t_start": started, "t_end": None}


def orchestrator_node(state):
    started = time.perf_counter()  # time_taken per request includes triage
    rows = normalize(state.get("raw_requests"))
    trace, requests, outcomes = [], [], {}
    if not rows:
        trace.append(trace_event("-", "Orchestrator", "empty_batch", "No requests received; nothing to dispatch"))

    specialties = known_specialties()
    valid = [r for r in rows if not validate(r)]
    triaged = {row["request_id"]: (tri, src) for row, tri, src in triage_rows(valid, specialties)}

    for row in rows:
        problems = validate(row)
        request = {**row, "patient_ref": None, "patient_is_new": False}
        if problems:
            request.update(type="malformed", priority=guess_priority(row["description"]), source="validation")
            reason = "malformed request: " + ", ".join(problems)
        else:
            tri, source = triaged[row["request_id"]]
            spec = tri.specialty_needed if tri.specialty_needed in specialties else "general_medicine"
            request.update(type=tri.request_type, priority=tri.priority, source=source,
                           patient_name=tri.patient_name, age=tri.age, condition=tri.condition,
                           specialty_needed=spec, ward_needed=tri.ward_needed,
                           staff_capability=tri.staff_capability, rationale=tri.rationale)
            if request["type"] != "malformed":
                pid, name, is_new = _resolve_patient(request, tri)
                request.update(patient_ref=pid, patient_name=name, patient_is_new=is_new)
            reason = "malformed request: " + tri.rationale if request["type"] == "malformed" else ""

        outcome = _new_outcome(request, started)
        if reason:
            outcome["unresolved"].append(reason)
        outcomes[request["request_id"]] = outcome
        requests.append(request)

    requests.sort(key=_sort_key)
    dispatch = []
    for request in requests:
        steps = plan_dispatch(request)
        dispatch += steps
        spawned = ", ".join(f"{AGENT_LABELS[s['node']]}({s['task']})" for s in steps) or "none"
        trace.append(trace_event(
            request["request_id"], "Orchestrator", "triaged",
            f"{request['type']} / {request['priority']} via {request.get('source')} -> Send: {spawned}"))

    return {"requests": requests, "dispatch": dispatch, "outcomes": outcomes,
            "round": 0, "trace": trace, "pending_followups": []}


def route_requests(state):
    """Conditional edge: one Send() per (request, agent) pair; count and types come from the batch."""
    by_id = {r["request_id"]: r for r in state.get("requests", [])}
    sends = [Send(step["node"], {"request": by_id[step["request_id"]], "task": step["task"], "round": 0})
             for step in state.get("dispatch", [])]
    return sends or "arbiter"
