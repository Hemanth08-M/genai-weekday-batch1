"""Escalation Agent: spawned only for items still unassigned; flags them for a human supervisor."""
import time

from ..graph.state import EscalationTask
from ..utils import now_iso, trace_event

WORKER = "Escalation Agent"


def _recommend(unresolved):
    text = " ".join(unresolved).lower()
    if "malformed" in text:
        return "Contact the reporter to get patient, location and what is needed"
    if "doctor" in text:
        return "Page on-call specialist or arrange transfer to a partner hospital"
    if "bed" in text:
        return "Expedite discharges or divert the ambulance / arrange inter-hospital transfer"
    if "staff" in text:
        return "Call in agency staff or reassign a team after their current task"
    return "Supervisor to review manually"


def escalation_agent(payload: EscalationTask) -> dict:
    request, unresolved = payload["request"], payload["unresolved"]
    record = {"request_id": request["request_id"], "priority": request["priority"], "type": request["type"],
              "unresolved": " | ".join(unresolved), "recommended_action": _recommend(unresolved),
              "flagged_at": now_iso(), "resolved_perf": time.perf_counter()}
    event = trace_event(request["request_id"], WORKER, "escalated",
                        f"flagged for human supervisor: {record['recommended_action']}")
    return {"escalations": [record], "trace": [event]}
