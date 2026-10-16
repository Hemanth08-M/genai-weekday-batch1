"""Patient List Agent: registers new patients or confirms existing ones."""
from ..tools.patient_tools import PATIENT_TOOLS
from .base import ResourceAgent, action, candidate, make_proposal


class PatientAgent(ResourceAgent):
    name = "Patient Agent"
    resource = "patient"
    tools = PATIENT_TOOLS

    def propose(self, request, task, round_no):
        pid = request["patient_ref"]
        name = request.get("patient_name") or f"Unknown ({request['request_id']})"
        if request.get("patient_is_new"):
            actions = [action("add_patient", patient_id=pid, name=name, age=request.get("age"),
                              condition=request.get("condition") or "",
                              specialty_needed=request.get("specialty_needed") or "",
                              priority=request["priority"], status="waiting")]
            cands = [candidate(pid, actions, f"registered {name} as {pid}")]
        else:
            cands = [candidate(pid, [], f"existing patient {pid} ({name}) confirmed")]
        return make_proposal(request, self.name, self.resource, round_no, cands, on_fail="escalate",
                             fail_reason="could not register patient")
