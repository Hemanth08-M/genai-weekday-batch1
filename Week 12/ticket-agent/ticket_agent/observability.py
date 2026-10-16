"""Langfuse setup and the one helper every chat turn goes through: trace_turn().

Vocabulary:
  trace        one chat turn (user message in, reply out)
  observation  one step inside a turn (LLM call, tool call, memory lookup ...)
  session      all turns of one conversation  (session_id)
  user         the person chatting            (user_id)
"""
import logging
import re
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator, Optional

from langfuse import Langfuse, propagate_attributes
from langfuse.langchain import CallbackHandler
from langfuse.types import MaskOtelSpansParams, MaskOtelSpansResult, OtelSpanPatch

from .config import settings

log = logging.getLogger(__name__)

# ---------------------------------------------------------------- masking
# Runs on every span just before export, so sensitive text never leaves the process.
MASK_PATTERNS = [
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"), "[EMAIL_REDACTED]"),
    (re.compile(r"\b(?:sk|pk)-[A-Za-z0-9_-]{16,}\b"), "[API_KEY_REDACTED]"),
]


def mask_otel_spans(*, params: MaskOtelSpansParams) -> Optional[MaskOtelSpansResult]:
    patches = {}
    for identifier, span in params.spans.items():
        replacements = {}
        for key, value in span.attributes.items():
            if isinstance(value, str):
                masked = value
                for pattern, token in MASK_PATTERNS:
                    masked = pattern.sub(token, masked)
                if masked != value:
                    replacements[key] = masked
        if replacements:
            patches[identifier] = OtelSpanPatch(set_attributes=replacements)
    return MaskOtelSpansResult(span_patches=patches)


# ---------------------------------------------------------------- client
_client: Optional[Langfuse] = None


def init_langfuse(check_auth: bool = True, **overrides) -> Langfuse:
    """Create the Langfuse client once (call this at startup, after the env is loaded)."""
    global _client
    if _client is None:
        _client = Langfuse(
            environment=settings.environment,
            release=settings.app_version,
            mask_otel_spans=mask_otel_spans,
            **overrides,
        )
        if check_auth:
            try:
                ok = _client.auth_check()
            except Exception as exc:  # network trouble (DNS, timeout): tracing is optional, don't block startup
                log.warning("Langfuse unreachable, continuing without confirmed auth: %s", exc)
                ok = True
            if not ok:
                raise RuntimeError(
                    "Langfuse authentication failed - check LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY / LANGFUSE_BASE_URL"
                )
    return _client


def client() -> Langfuse:
    if _client is None:
        raise RuntimeError("Langfuse is not initialised - call init_langfuse() at startup.")
    return _client


def shutdown() -> None:
    """Flush buffered events and stop background threads. Call on exit."""
    if _client is not None:
        _client.flush()
        _client.shutdown()


def lf_config(run_name: str | None = None) -> dict:
    """Pass as `config=` to any LangChain invoke() so the call appears (nested) in the current trace."""
    cfg: dict = {"callbacks": [CallbackHandler()]}
    if run_name:
        cfg["run_name"] = run_name
    return cfg


# ---------------------------------------------------------------- the traced turn
@dataclass
class TurnRecord:
    """The caller fills this in; trace_turn writes it to the trace when the turn ends."""
    reply: str = ""
    tool_calls: list[str] = field(default_factory=list)
    trace_url: str = ""  # filled in when the turn ends


@contextmanager
def trace_turn(*, user_msg: str, user_id: str, session_id: str, tags: list[str]) -> Iterator[TurnRecord]:
    """One chat turn = one Langfuse trace.

    - opens the root span `handle-chat-turn` (input = the user message)
    - stamps user_id / session_id / tags / version on EVERY observation created inside
    - on success: records the reply and scores `turn_outcome=success` + `tool_calls_count`
    - on exception: marks the span ERROR, scores `turn_outcome=error`, re-raises
    """
    lf = client()
    turn = TurnRecord()
    trace_id: str | None = None
    try:
        with lf.start_as_current_observation(name="handle-chat-turn", as_type="span", input=user_msg) as root:
            trace_id = root.trace_id
            with propagate_attributes(
                user_id=user_id,
                session_id=session_id,
                trace_name="handle-chat-turn",
                tags=tags,
                version=settings.app_version,
                metadata={"app_version": settings.app_version},
            ):
                try:
                    yield turn
                except Exception as exc:
                    root.update(level="ERROR", status_message=f"{type(exc).__name__}: {exc}")
                    lf.score_current_trace(name="turn_outcome", value="error", data_type="CATEGORICAL")
                    raise
                else:
                    root.update(output=turn.reply, metadata={"tool_calls": turn.tool_calls})
                    lf.score_current_trace(name="turn_outcome", value="success", data_type="CATEGORICAL")
                    lf.score_current_trace(name="tool_calls_count", value=float(len(turn.tool_calls)), data_type="NUMERIC")
    finally:
        # Flush every turn: right for a CLI/demo. In a long-running service, drop this and flush on shutdown.
        lf.flush()
        if trace_id:
            try:
                turn.trace_url = lf.get_trace_url(trace_id=trace_id) or ""
                log.info("trace: %s", turn.trace_url)
            except Exception:  # building the URL needs an API call; never let it break a chat turn
                pass
