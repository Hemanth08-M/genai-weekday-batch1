"""Reallocation Worker: spawned only for ER cases when no doctor is free."""
from ..agents.base import action, candidate, describe, make_proposal
from ..graph.state import FollowupTask
from ..tools.doctor_tools import find_eligible_doctors, list_doctors
from ..tools.patient_tools import get_patient
from ..utils import parse_ts, trace_event

WORKER = "Reallocation Worker"


def _preempt_candidates(request, specialty):
    """Pull a specialist off routine work: hand their routine patients to a free doctor if possible."""
    at = parse_ts(request["timestamp"])
    pid = request["patient_ref"]
    cands = []
    for doc in list_doctors.invoke({"specialty": specialty})["doctors"]:
        end = parse_ts(doc["shift_end"])
        if end and at and end <= at:
            continue
        caseload = [get_patient.invoke({"patient_id": p})["patient"]
                    for p in doc["current_patient_ids"].split("|") if p]
        caseload = [p for p in caseload if p and p["status"] != "discharged"]
        if any(p["priority"] == "emergency" for p in caseload):
            continue  # already handling an emergency
        actions, notes = [], []
        for patient in caseload:
            targets = [d for d in find_eligible_doctors.invoke(
                {"specialty": None, "request_time": request["timestamp"], "is_er": False})["eligible"]
                if d["doctor_id"] != doc["doctor_id"]]
            if targets:
                t = targets[0]["doctor_id"]
                actions += [action("release_doctor", doctor_id=doc["doctor_id"], patient_id=patient["patient_id"]),
                            action("assign_doctor", doctor_id=t, patient_id=patient["patient_id"]),
                            action("link_patient", patient_id=patient["patient_id"], doctor_id=t)]
                notes.append(f"{patient['patient_id']} handed to {t}")
            else:
                notes.append(f"{patient['patient_id']} follow-up deferred")
        actions += [action("assign_doctor", doctor_id=doc["doctor_id"], patient_id=pid, is_er=True, override=True),
                    action("link_patient", patient_id=pid, doctor_id=doc["doctor_id"])]
        detail = "; ".join(notes) or "no routine caseload"
        cands.append(candidate(doc["doctor_id"], actions,
                               f"pulled {doc['name']} ({specialty}) off routine work for ER ({detail})"))
    return cands


def _any_doctor_candidates(request):
    """Fallback: any available doctor stabilises the ER patient (30-min rule waived for ER)."""
    pid = request["patient_ref"]
    found = find_eligible_doctors.invoke({"specialty": None, "request_time": request["timestamp"], "is_er": True})
    return [candidate(d["doctor_id"],
                      [action("assign_doctor", doctor_id=d["doctor_id"], patient_id=pid, is_er=True),
                       action("link_patient", patient_id=pid, doctor_id=d["doctor_id"])],
                      f"no {request['specialty_needed']} free; {d['name']} ({d['specialty']}) stabilises ER patient")
            for d in found["eligible"]]


def reallocation_worker(payload: FollowupTask) -> dict:
    request, rnd = payload["request"], payload["round"]
    specialty = payload["need"].get("specialty") or request["specialty_needed"]
    cands = _preempt_candidates(request, specialty) + _any_doctor_candidates(request)
    proposal = make_proposal(request, WORKER, "doctor", rnd, cands, on_fail="escalate",
                             fail_reason="no doctor could be reallocated")
    return {"proposals": [proposal],
            "trace": [trace_event(request["request_id"], WORKER, "proposed", describe(proposal))]}
