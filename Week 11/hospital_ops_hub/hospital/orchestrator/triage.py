"""Triage: derive request type and priority with gpt-4o-mini (keyword rules as a safety net)."""
from ..llm import get_llm, llm_available
from ..models import TriageResult

SYSTEM_PROMPT = """You are the triage orchestrator of a hospital operations hub.
Classify ONE incoming request.

Request types:
- new_patient: a walk-in / new patient who needs a doctor, not life-threatening.
- er_emergency: life-threatening arrival needing an ER doctor now (chest pain with sweating,
  unconscious, seizures, stroke, severe bleeding, ambulance arrival in critical state).
- emergency_admission: a patient who urgently needs an ICU/ER bed admission (e.g. post-op needs ICU).
- routine_bed: an existing/waiting patient needs a normal ward bed.
- cleaning: spills or cleaning. staff_capability = "biohazard" ONLY for blood, contamination or
  explicitly specialised cleaning; vomit and ordinary spills are "standard".
- patient_handling: moving a patient (wheelchair / stretcher transfer, porter needed).
  staff_capability = "wheelchair" or "stretcher".
- malformed: no actionable information.

Priority: emergency = life-threatening now; urgent = needs action soon (ICU admission, biohazard
cleaning, moving an ICU patient); routine = everything else.

Hospital specialties available: {specialties}. Set specialty_needed to one of these.
Map conditions sensibly (heart -> cardiology, seizures/stroke/head -> neurology,
bones/fracture/knee -> orthopedics, rash/fever/anything else -> general_medicine).
Set ward_needed for bed requests (ER for ER cases, ICU for ICU, General for ward beds).
For new patients set staff_capability = "registration".
Only extract names/ids/ages that are present in the text. patient_name must be a proper name
(e.g. "Neha Iyer"); descriptions like "man around 60" or "young woman" give patient_name = null."""

KEYWORD_RULES = [
    ("er_emergency", "emergency", ("chest pain", "unconscious", "seizure", "ambulance", "stroke", "not breathing")),
    ("emergency_admission", "urgent", ("icu bed", "post-op", "admission")),
    ("cleaning", "urgent", ("blood", "biohazard", "contamination")),
    ("cleaning", "routine", ("spill", "cleaning", "clean")),
    ("patient_handling", "routine", ("wheelchair", "stretcher", "porter", "transfer")),
    ("routine_bed", "routine", ("ward bed", "general ward bed", "needs a bed")),
    ("new_patient", "routine", ("new patient", "walked in", "needs a doctor")),
]


def rule_based_triage(row):
    """Deterministic fallback when the LLM is unavailable or fails."""
    text = row["description"].lower()
    for rtype, priority, keys in KEYWORD_RULES:
        if any(k in text for k in keys):
            cap = None
            if rtype == "cleaning":
                cap = "biohazard" if priority == "urgent" else "standard"
            elif rtype == "patient_handling":
                cap = "stretcher" if "stretcher" in text else "wheelchair"
            return TriageResult(request_type=rtype, priority=priority, staff_capability=cap,
                                specialty_needed="general_medicine",
                                rationale="keyword rules (LLM unavailable)")
    return TriageResult(request_type="malformed", priority="routine", rationale="no rule matched")


def triage_rows(rows, specialties):
    """Classify every row. Returns list of (row, TriageResult, source)."""
    if not rows:
        return []
    results = [None] * len(rows)
    if llm_available():
        classifier = get_llm().with_structured_output(TriageResult, method="function_calling")
        system = SYSTEM_PROMPT.format(specialties=", ".join(specialties))
        prompts = [[("system", system),
                    ("human", f"Request {r['request_id']} at {r['timestamp']} from {r['reported_by'] or 'unknown'} "
                              f"({r['location'] or 'no location'}):\n{r['description']}")] for r in rows]
        results = classifier.batch(prompts, config={"max_concurrency": 8}, return_exceptions=True)
    out = []
    for row, result in zip(rows, results):
        if isinstance(result, TriageResult):
            out.append((row, result, "llm"))
        else:
            out.append((row, rule_based_triage(row), "rules"))
    return out
