"""Tool registry: every resource change goes through one of these LangChain tools."""
from ..guardrails import guarded, validate_tool_args
from .bed_tools import BED_READ_TOOLS, BED_TOOLS
from .doctor_tools import DOCTOR_READ_TOOLS, DOCTOR_TOOLS
from .patient_tools import PATIENT_READ_TOOLS, PATIENT_TOOLS
from .staff_tools import STAFF_READ_TOOLS, STAFF_TOOLS

ALL_TOOLS = PATIENT_TOOLS + DOCTOR_TOOLS + BED_TOOLS + STAFF_TOOLS
# Read tools feed the Q&A LLM, so their output is sanitised (indirect-injection guard).
READ_ONLY_TOOLS = [guarded(t) for t in
                   PATIENT_READ_TOOLS + DOCTOR_READ_TOOLS + BED_READ_TOOLS + STAFF_READ_TOOLS]
TOOL_REGISTRY = {t.name: t for t in ALL_TOOLS}


def run_tool(name, args):
    """Invoke a registered tool by name (used by the Resource Arbiter to commit actions)."""
    if name not in TOOL_REGISTRY:
        raise ValueError(f"Unknown tool '{name}'")
    validate_tool_args(name, args)
    return TOOL_REGISTRY[name].invoke(args)
