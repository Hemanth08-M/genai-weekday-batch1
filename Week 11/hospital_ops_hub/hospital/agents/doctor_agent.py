"""Doctor List Agent: finds eligible doctors by specialty, load and shift-end rule."""
from ..tools.doctor_tools import DOCTOR_TOOLS, find_eligible_doctors
from .base import ResourceAgent, action, candidate, make_proposal


class DoctorAgent(ResourceAgent):
    name = "Doctor Agent"
    resource = "doctor"
    tools = DOCTOR_TOOLS

    def propose(self, request, task, round_no):
        is_er = task == "assign_er"
        specialty = request["specialty_needed"]
        pid = request["patient_ref"]
        found = find_eligible_doctors.invoke(
            {"specialty": specialty, "request_time": request["timestamp"], "is_er": is_er})
        cands = [
            candidate(d["doctor_id"],
                      [action("assign_doctor", doctor_id=d["doctor_id"], patient_id=pid, is_er=is_er),
                       action("link_patient", patient_id=pid, doctor_id=d["doctor_id"])],
                      f"{d['name']} ({specialty}, load {d['current_patient_count']})")
            for d in found["eligible"]
        ]
        rejected = "; ".join(r["reason"] for r in found["rejected"])
        if cands:
            fail_reason = f"every eligible {specialty} doctor was taken"
        else:
            fail_reason = f"no free {specialty} doctor ({rejected or 'none on staff'})"
        return make_proposal(
            request, self.name, self.resource, round_no, cands,
            on_fail="reallocation" if is_er else "queue",
            fail_reason=fail_reason,
            need={"kind": "reallocation", "specialty": specialty},
        )
