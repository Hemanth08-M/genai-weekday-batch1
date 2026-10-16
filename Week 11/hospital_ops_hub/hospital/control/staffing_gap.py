"""Staffing Gap Resolver: spawned only when no staff was found; checks float pool and on-call."""
from ..agents.base import action, candidate, describe, make_proposal
from ..graph.state import FollowupTask
from ..tools.staff_tools import has_capability, list_available_staff, list_staff
from ..utils import trace_event

WORKER = "Staffing Gap Resolver"


def staffing_gap_resolver(payload: FollowupTask) -> dict:
    request, need, rnd = payload["request"], payload["need"], payload["round"]
    capability = need.get("capability")
    pool = []
    if capability != "biohazard":  # biohazard stays with the specialised team only
        pool += list_available_staff.invoke({"role": "float_pool", "capability": None})["staff"]
    pool += [s for s in list_staff.invoke({"status": "on_call"})["staff"] if has_capability(s, capability)]
    cands = [candidate(s["staff_id"],
                       [action("assign_staff", staff_id=s["staff_id"], request_id=request["request_id"])],
                       f"covered by {s['name']} ({s['role']}, {s['status']})")
             for s in pool]
    on_fail = "escalate" if request["priority"] in ("emergency", "urgent") else "queue"
    proposal = make_proposal(request, WORKER, "staff", rnd, cands, on_fail=on_fail,
                             fail_reason=f"float pool and on-call exhausted for {capability}")
    return {"proposals": [proposal],
            "trace": [trace_event(request["request_id"], WORKER, "proposed", describe(proposal))]}
