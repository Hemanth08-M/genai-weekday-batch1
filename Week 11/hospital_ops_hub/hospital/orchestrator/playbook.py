"""Which resource agents the manager spawns for each request type (count comes from the batch)."""

PLAYBOOK = {
    "new_patient": [("patient_agent", "register"), ("doctor_agent", "assign"), ("staff_agent", "clerk")],
    "er_emergency": [("patient_agent", "register"), ("doctor_agent", "assign_er"),
                     ("bed_agent", "assign_er"), ("staff_agent", "er_support")],
    "emergency_admission": [("patient_agent", "register"), ("bed_agent", "emergency_admit")],
    "routine_bed": [("patient_agent", "register"), ("bed_agent", "routine")],
    "cleaning": [("staff_agent", "housekeeping")],
    "patient_handling": [("patient_agent", "register"), ("staff_agent", "handling")],
}

AGENT_LABELS = {"patient_agent": "Patient Agent", "doctor_agent": "Doctor Agent",
                "bed_agent": "Bed Agent", "staff_agent": "Staff Agent"}


def plan_dispatch(request):
    """List of {node, task} for one triaged request; malformed/unknown types get none."""
    steps = []
    for node, task in PLAYBOOK.get(request["type"], []):
        if node == "patient_agent" and not request.get("patient_ref"):
            continue
        steps.append({"node": node, "task": task, "request_id": request["request_id"]})
    return steps
