"""LangGraph state and the payload types carried by Send()."""
import operator
from typing import Annotated, TypedDict


def merge_dicts(left, right):
    return {**(left or {}), **(right or {})}


class HubState(TypedDict, total=False):
    raw_requests: list[dict]                               # rows as received (CSV / chat)
    requests: list[dict]                                   # triaged, emergencies first
    dispatch: list[dict]                                   # which agent the manager spawns per request
    proposals: Annotated[list[dict], operator.add]          # claims from agents / workers
    outcomes: Annotated[dict, merge_dicts]                  # request_id -> result so far
    pending_followups: list[dict]                          # Reallocation / Staffing Gap work
    round: int
    trace: Annotated[list[dict], operator.add]
    escalations: Annotated[list[dict], operator.add]
    log_rows: list[dict]
    plan_summary: str


class AgentTask(TypedDict):
    """Send() payload for the four resource agents."""
    request: dict
    task: str
    round: int


class FollowupTask(TypedDict):
    """Send() payload for the Reallocation Worker and Staffing Gap Resolver."""
    request: dict
    need: dict
    round: int


class EscalationTask(TypedDict):
    """Send() payload for the Escalation Agent."""
    request: dict
    unresolved: list[str]
