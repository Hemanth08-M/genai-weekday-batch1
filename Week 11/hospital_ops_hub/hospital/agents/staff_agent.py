"""Staff Agent with its dispatchers: clerk, ER support, housekeeping, patient handling."""
from ..tools.staff_tools import STAFF_TOOLS, list_available_staff
from .base import ResourceAgent, action, candidate, make_proposal


class StaffAgent(ResourceAgent):
    name = "Staff Agent"
    resource = "staff"
    tools = STAFF_TOOLS

    def _needs(self, request, task):
        """Return (dispatcher label, roles to search, capability)."""
        if task == "clerk":
            return "Clerk Dispatch", ["clerk"], "registration"
        if task == "er_support":
            return "ER Support Dispatch", ["porter", "nurse"], "stretcher"
        if task == "housekeeping":
            cap = "biohazard" if request.get("staff_capability") == "biohazard" else "standard"
            label = "Housekeeping Dispatcher" + (" (biohazard team)" if cap == "biohazard" else "")
            return label, ["cleaning"], cap
        cap = request.get("staff_capability") if request.get("staff_capability") in ("wheelchair", "stretcher") else "wheelchair"
        return "Handling Dispatcher", ["porter", "nurse"], cap

    def propose(self, request, task, round_no):
        label, roles, capability = self._needs(request, task)
        pool = []
        for role in roles:
            pool += list_available_staff.invoke({"role": role, "capability": capability})["staff"]
        if capability == "standard":
            # keep the biohazard-capable team free for specialised spills
            pool.sort(key=lambda s: "biohazard" in s["capability"])
        cands = [candidate(s["staff_id"],
                           [action("assign_staff", staff_id=s["staff_id"], request_id=request["request_id"])],
                           f"{s['name']} ({s['role']}, {capability})")
                 for s in pool]
        return make_proposal(
            request, f"{self.name} > {label}", self.resource, round_no, cands,
            on_fail="staffing_gap", fail_reason=f"no available {'/'.join(roles)} with {capability}",
            need={"kind": "staffing_gap", "roles": roles, "capability": capability},
        )
