"""Resource Arbiter: commits claims by priority then timestamp; losers fall back or get follow-ups."""
import time
from collections import defaultdict
from copy import deepcopy

from langgraph.types import Send

from ..config import PRIORITY_RANK, RESOURCE_ORDER
from ..tools import run_tool
from ..utils import trace_event

FOLLOWUP_NODES = {"reallocation": "reallocation_worker", "staffing_gap": "staffing_gap_resolver"}


def _order(p):
    return (PRIORITY_RANK.get(p["priority"], 9), p["timestamp"] or "9999", p["request_id"],
            RESOURCE_ORDER.get(p["resource"], 9))


def _execute(actions):
    for act in actions:
        result = run_tool(act["tool"], act["args"])
        if not result.get("ok"):
            return False, result.get("error", f"{act['tool']} failed")
    return True, ""


def _record_win(outcome, proposal, cand):
    if proposal["resource"] == "staff":
        outcome["staff"].append(cand["id"])
    else:
        outcome[proposal["resource"]] = cand["id"]
    outcome["notes"].append(f"{proposal['worker']}: {cand['note']}")


def arbiter_node(state):
    rnd = state.get("round", 0)
    proposals = sorted([p for p in state.get("proposals", []) if p["round"] == rnd], key=_order)
    outcomes = deepcopy(state.get("outcomes", {}))
    requests = {r["request_id"]: r for r in state.get("requests", [])}
    trace, followups = [], []

    # Detect double claims on the same exclusive resource (first choice of each proposal)
    first_choice = defaultdict(list)
    for p in proposals:
        if p["resource"] != "patient" and p["candidates"]:
            first_choice[(p["resource"], p["candidates"][0]["id"])].append(p)
    for (resource, rid), claims in first_choice.items():
        if len(claims) > 1:
            winner, losers = claims[0], [c["request_id"] for c in claims[1:]]
            trace.append(trace_event(
                winner["request_id"], "Resource Arbiter", "conflict",
                f"{resource} {rid} claimed by {', '.join(c['request_id'] for c in claims)}; "
                f"{winner['request_id']} wins ({winner['priority']}, {winner['timestamp']}); "
                f"{', '.join(losers)} try next option"))

    taken = set()
    for p in proposals:
        outcome = outcomes[p["request_id"]]
        if p["worker"] not in outcome["workers"]:
            outcome["workers"].append(p["worker"])
        won, errors = None, []
        for cand in p["candidates"]:
            key = (p["resource"], cand["id"])
            if p["resource"] != "patient" and key in taken:
                errors.append(f"{cand['id']} already granted to a higher-priority request")
                continue
            ok, err = _execute(cand["actions"])
            if ok:
                won = cand
                taken.add(key)
                break
            errors.append(err)

        if won:
            _record_win(outcome, p, won)
            trace.append(trace_event(p["request_id"], "Resource Arbiter", "committed",
                                     f"{p['resource']} {won['id']} via {p['worker']}"))
        else:
            reason = p["fail_reason"] + (f" [{'; '.join(errors)}]" if errors else "")
            on_fail = p["on_fail"]
            if on_fail in FOLLOWUP_NODES and rnd == 0:
                followups.append({"node": FOLLOWUP_NODES[on_fail], "request": requests[p["request_id"]],
                                  "need": {**p["need"], "resource": p["resource"]}})
                outcome["notes"].append(f"{p['worker']}: {reason} -> spawning {FOLLOWUP_NODES[on_fail]}")
            elif on_fail == "queue":
                outcome["queued"].append(f"{p['resource']}: {reason}")
            elif on_fail != "skip":
                outcome["unresolved"].append(f"{p['resource']}: {reason}")
            trace.append(trace_event(p["request_id"], "Resource Arbiter", "unassigned",
                                     f"{p['resource']}: {reason} -> {on_fail}"))
        outcome["t_end"] = time.perf_counter()

    return {"outcomes": outcomes, "round": rnd + 1, "pending_followups": followups, "trace": trace}


def route_after_arbiter(state):
    """Spawn follow-up workers, then Escalation Agents, only when needed; else synthesise."""
    followups = state.get("pending_followups") or []
    if followups:
        return [Send(f["node"], {"request": f["request"], "need": f["need"], "round": state["round"]})
                for f in followups]
    requests = {r["request_id"]: r for r in state.get("requests", [])}
    unresolved = [o for o in state.get("outcomes", {}).values() if o["unresolved"]]
    if unresolved:
        return [Send("escalation_agent", {"request": requests[o["request_id"]], "unresolved": o["unresolved"]})
                for o in unresolved]
    return "synthesizer"
