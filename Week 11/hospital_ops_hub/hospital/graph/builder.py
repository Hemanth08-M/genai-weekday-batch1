"""Assemble the Hospital Operations Hub graph.

orchestrator --Send()--> patient/doctor/bed/staff agents (only those each request needs)
             --> arbiter --Send()--> reallocation_worker / staffing_gap_resolver (only on shortage) --> arbiter
                         --Send()--> escalation_agent (only for unassigned items) --> synthesizer --> END
"""
from langgraph.graph import END, START, StateGraph

from ..agents import AGENTS
from ..control.arbiter import arbiter_node, route_after_arbiter
from ..control.escalation import escalation_agent
from ..control.reallocation import reallocation_worker
from ..control.staffing_gap import staffing_gap_resolver
from ..control.synthesizer import synthesizer_node
from ..orchestrator.manager import orchestrator_node, route_requests
from .state import HubState


def build_graph():
    g = StateGraph(HubState)
    g.add_node("orchestrator", orchestrator_node)
    for name, agent in AGENTS.items():
        g.add_node(name, agent.node)
    g.add_node("arbiter", arbiter_node)
    g.add_node("reallocation_worker", reallocation_worker)
    g.add_node("staffing_gap_resolver", staffing_gap_resolver)
    g.add_node("escalation_agent", escalation_agent)
    g.add_node("synthesizer", synthesizer_node)

    g.add_edge(START, "orchestrator")
    g.add_conditional_edges("orchestrator", route_requests, [*AGENTS, "arbiter"])
    for name in AGENTS:
        g.add_edge(name, "arbiter")
    g.add_conditional_edges("arbiter", route_after_arbiter,
                            ["reallocation_worker", "staffing_gap_resolver", "escalation_agent", "synthesizer"])
    g.add_edge("reallocation_worker", "arbiter")
    g.add_edge("staffing_gap_resolver", "arbiter")
    g.add_edge("escalation_agent", "synthesizer")
    g.add_edge("synthesizer", END)
    return g.compile()
