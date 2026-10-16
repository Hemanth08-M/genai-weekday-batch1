"""Shared shape for the four resource manager agents.

Agents run in parallel (spawned by the manager with Send) and only READ their list.
They return ranked candidate claims; the Resource Arbiter commits the winners
through the write tools, so two agents can never grab the same doctor/bed/porter.
"""
from ..graph.state import AgentTask
from ..utils import trace_event


def action(tool_name, **args):
    return {"tool": tool_name, "args": args}


def candidate(resource_id, actions, note):
    return {"id": resource_id, "actions": actions, "note": note}


def make_proposal(request, worker, resource, round_no, candidates, on_fail, fail_reason="", need=None):
    return {
        "request_id": request["request_id"], "priority": request["priority"],
        "timestamp": request["timestamp"], "round": round_no, "worker": worker,
        "resource": resource, "candidates": candidates, "on_fail": on_fail,
        "fail_reason": fail_reason, "need": need or {},
    }


def describe(proposal):
    if proposal["candidates"]:
        ids = ", ".join(c["id"] for c in proposal["candidates"][:3])
        return f"proposes {proposal['resource']} [{ids}]"
    return f"no {proposal['resource']} available ({proposal['fail_reason']}) -> on_fail={proposal['on_fail']}"


class ResourceAgent:
    name = "Resource Agent"
    resource = ""
    tools = []

    def propose(self, request, task, round_no):
        raise NotImplementedError

    def node(self, payload: AgentTask) -> dict:
        """LangGraph node entry point; receives the Send() payload."""
        proposal = self.propose(payload["request"], payload["task"], payload.get("round", 0))
        event = trace_event(proposal["request_id"], proposal["worker"], "proposed", describe(proposal))
        return {"proposals": [proposal], "trace": [event]}
