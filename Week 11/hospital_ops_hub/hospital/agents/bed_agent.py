"""Bed Manager Agent: free beds by ward; frees a discharge-ready bed only when ICU/ER is full."""
from ..tools.bed_tools import BED_TOOLS, list_discharge_ready_beds, list_free_beds
from .base import ResourceAgent, action, candidate, make_proposal

# task -> (default ward, may release discharge-ready bed, what to do when nothing is free)
BED_TASKS = {
    "assign_er": ("ER", True, "escalate"),
    "emergency_admit": ("ICU", True, "escalate"),
    "routine": ("General", False, "queue"),
}


class BedAgent(ResourceAgent):
    name = "Bed Agent"
    resource = "bed"
    tools = BED_TOOLS

    def propose(self, request, task, round_no):
        default_ward, may_release, on_fail = BED_TASKS[task]
        ward = default_ward if task == "assign_er" else (request.get("ward_needed") or default_ward)
        pid = request["patient_ref"]

        cands = [
            candidate(b["bed_id"],
                      [action("assign_bed", bed_id=b["bed_id"], patient_id=pid),
                       action("link_patient", patient_id=pid, bed_id=b["bed_id"])],
                      f"{ward} bed {b['bed_id']}")
            for b in list_free_beds.invoke({"ward": ward})["beds"]
        ]
        if not cands and may_release and ward in ("ICU", "ER"):
            for b in list_discharge_ready_beds.invoke({"ward": ward})["beds"]:
                old = b["patient_id"]
                actions = [action("release_bed", bed_id=b["bed_id"]),
                           action("update_patient_status", patient_id=old, status="discharged")]
                if b["doctor_id"]:
                    actions.append(action("release_doctor", doctor_id=b["doctor_id"], patient_id=old))
                actions += [action("assign_bed", bed_id=b["bed_id"], patient_id=pid),
                            action("link_patient", patient_id=pid, bed_id=b["bed_id"])]
                cands.append(candidate(
                    b["bed_id"], actions,
                    f"{ward} full -> discharged ready patient {old} ({b['patient_name']}) to free {b['bed_id']}"))

        return make_proposal(request, self.name, self.resource, round_no, cands, on_fail=on_fail,
                             fail_reason=f"{ward} ward full" + (", no discharge-ready bed" if may_release else ""))
