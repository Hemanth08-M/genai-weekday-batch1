"""Synthesizer: builds fixed-schema log rows, persists them, and writes the current plan."""
import json
import time

from ..llm import get_llm, llm_available
from ..reporting.shift_log import get_shift_log
from ..utils import trace_event

BRIEFING_PROMPT = """You are the hospital operations manager. In 2-3 sentences, brief the duty
supervisor on this batch using ONLY these facts: what was handled, what is waiting, and what
needs their attention. Do not restate counts or invent ids.

FACTS:
{facts}"""

STATUS_ICON = {"assigned": "✅", "queued": "⏳", "escalated": "🚨"}


def _status(outcome, escalated):
    if outcome["request_id"] in escalated:
        return "escalated"
    if outcome["queued"]:
        return "queued"
    return "assigned"


def build_log_rows(state, shift_id):
    escalated = {e["request_id"]: e for e in state.get("escalations", [])}
    outcomes = state.get("outcomes", {})
    now = time.perf_counter()
    rows = []
    for request in state.get("requests", []):
        o = outcomes[request["request_id"]]
        end = escalated.get(o["request_id"], {}).get("resolved_perf") or o["t_end"] or now
        patient = o["patient"]
        if patient and request.get("patient_name"):
            patient = f"{patient} ({request['patient_name']})"
        workers = list(dict.fromkeys(o["workers"] + (["Escalation Agent"] if o["request_id"] in escalated else [])))
        rows.append({
            "request_id": o["request_id"], "type": o["type"], "priority": o["priority"],
            "patient": patient, "doctor": o["doctor"], "bed": o["bed"], "staff": "|".join(o["staff"]),
            "status": _status(o, escalated), "time_taken": round(end - o["t_start"], 3),
            "reason": "; ".join(o["notes"] + o["queued"] + o["unresolved"]),
            "timestamp": o["timestamp"], "description": o["description"], "workers": " > ".join(workers),
            "retry_of": o.get("retry_of", ""), "shift_id": shift_id,
        })
    return rows


def deterministic_plan(rows, state):
    if not rows:
        return "**No requests in this batch.** Nothing was dispatched."
    counts = {s: sum(r["status"] == s for r in rows) for s in STATUS_ICON}
    lines = [f"**{counts['assigned']} assigned · {counts['queued']} queued · {counts['escalated']} escalated**",
             "", "#### Actions taken (emergencies first)"]
    for r in rows:
        got = ", ".join(f"{k} `{r[k]}`" for k in ("patient", "doctor", "bed", "staff") if r[k]) or "nothing assigned"
        lines.append(f"- {STATUS_ICON[r['status']]} **{r['request_id']}** {r['type']} / {r['priority']} → {got}")
    conflicts = [t["detail"] for t in state.get("trace", []) if t["event"] == "conflict"]
    if conflicts:
        lines += ["", "#### Conflicts resolved by the Resource Arbiter"] + [f"- {c}" for c in conflicts]
    escalations = state.get("escalations", [])
    if escalations:
        lines += ["", "#### Needs supervisor attention"]
        lines += [f"- **{e['request_id']}**: {e['unresolved']} → _{e['recommended_action']}_" for e in escalations]
    return "\n".join(lines)


def write_plan(rows, state):
    plan = deterministic_plan(rows, state)
    if not rows or not llm_available():
        return plan
    facts = [{k: r[k] for k in ("request_id", "type", "priority", "status", "reason")} for r in rows]
    try:
        briefing = get_llm().invoke(BRIEFING_PROMPT.format(facts=json.dumps(facts, indent=1))).content
        return f"> {briefing.strip()}\n\n{plan}"
    except Exception as exc:  # keep the run alive if the LLM call fails
        return plan + f"\n\n_(LLM briefing unavailable: {exc})_"


def synthesizer_node(state):
    shift_log = get_shift_log()
    rows = build_log_rows(state, shift_log.shift_id)
    plan = write_plan(rows, state)
    done = trace_event("-", "Synthesizer", "report",
                       f"{len(rows)} request(s) written to shift {shift_log.shift_id} log")
    shift_log.append("request_log", rows)
    shift_log.append("worker_trace", state.get("trace", []) + [done])
    shift_log.append("escalations", state.get("escalations", []))
    return {"log_rows": rows, "plan_summary": plan, "trace": [done]}
