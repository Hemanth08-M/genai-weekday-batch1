"""Indirect-injection defence: sanitise what tools return to the LLM and validate tool-call arguments.
Stored free text (patient name/condition, CSV descriptions) is untrusted data, never instructions."""
import json

from langchain_core.tools import StructuredTool

from ..config import GUARDRAILS_ENABLED
from .injection import detect_injection
from .pipeline import CLINICAL_CATEGORIES, log_block
from .guard_model import GuardUnavailable, classify

BLOCKED_TEXT = "[blocked: suspected injected instructions in stored data]"
UNAVAILABLE_TEXT = "[tool output withheld: safety service unreachable]"


def _redact(value, hits):
    """Replace every string leaf that trips the injection heuristics."""
    if isinstance(value, str):
        found = detect_injection(value)
        if found:
            hits.extend(found)
            return BLOCKED_TEXT
        return value
    if isinstance(value, dict):
        return {k: _redact(v, hits) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact(v, hits) for v in value]
    return value


def guard_tool_output(output, tool_name="tool"):
    """Redact injected leaves, then run Llama Guard over the remaining payload. Fails closed."""
    if not GUARDRAILS_ENABLED:
        return output
    hits = []
    cleaned = _redact(output, hits)
    if hits:
        log_block("tool_output", tool_name, ",".join(sorted(set(hits))), json.dumps(output, default=str))
    payload = cleaned if isinstance(cleaned, str) else json.dumps(cleaned, default=str)
    if payload and BLOCKED_TEXT not in payload:
        try:
            verdict = classify(payload, "User")
        except GuardUnavailable:
            log_block("tool_output", tool_name, "guard_unavailable", payload)
            return UNAVAILABLE_TEXT
        cats = [c for c in verdict.categories if c not in CLINICAL_CATEGORIES]
        if not verdict.safe and cats:
            log_block("tool_output", tool_name, "llama_guard:" + ",".join(cats), payload)
            return BLOCKED_TEXT
    return cleaned


def validate_tool_args(name, args):
    """Reject tool calls whose string arguments carry injection payloads. Raises ValueError."""
    if not GUARDRAILS_ENABLED:
        return
    hits = []
    _redact(args, hits)
    if hits:
        log_block("tool_args", name, ",".join(sorted(set(hits))), json.dumps(args, default=str))
        raise ValueError(f"Tool call '{name}' blocked: suspicious argument content")


def guarded(tool):
    """Wrap a read-only LangChain tool so its output is sanitised before the LLM sees it."""
    inner = tool.func

    def run(*args, **kwargs):
        validate_tool_args(tool.name, kwargs)
        return guard_tool_output(inner(*args, **kwargs), tool.name)

    return StructuredTool.from_function(func=run, name=tool.name, description=tool.description,
                                        args_schema=tool.args_schema)
