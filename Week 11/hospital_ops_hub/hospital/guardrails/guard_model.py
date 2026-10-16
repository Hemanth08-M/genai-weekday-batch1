"""Llama Guard 3 1B (served by Ollama) as a safety classifier."""
from dataclasses import dataclass, field
from functools import lru_cache

from langchain_ollama import ChatOllama

from ..config import GUARD_MODEL, OLLAMA_BASE_URL

CATEGORY_NAMES = {
    "S1": "violent crimes", "S2": "non-violent crimes", "S3": "sex crimes", "S4": "child exploitation",
    "S5": "defamation", "S6": "specialized advice", "S7": "privacy", "S8": "intellectual property",
    "S9": "indiscriminate weapons", "S10": "hate", "S11": "self-harm", "S12": "sexual content",
    "S13": "elections", "S14": "code interpreter abuse",
}


class GuardUnavailable(RuntimeError):
    """Ollama or the guard model could not be reached (callers fail closed)."""


@dataclass
class GuardVerdict:
    safe: bool
    categories: list = field(default_factory=list)
    raw: str = ""


@lru_cache(maxsize=1)
def get_guard_llm():
    return ChatOllama(model=GUARD_MODEL, base_url=OLLAMA_BASE_URL, temperature=0, num_predict=24)


def parse_verdict(raw):
    """Llama Guard answers 'safe' or 'unsafe\\nS1,S2'."""
    lines = [ln.strip() for ln in str(raw).strip().splitlines() if ln.strip()]
    if not lines:
        raise GuardUnavailable("empty guard response")
    if lines[0].lower().startswith("safe"):
        return GuardVerdict(True, [], str(raw))
    cats = [c.strip().upper() for c in " ".join(lines[1:]).split(",") if c.strip()]
    return GuardVerdict(False, cats, str(raw))


def classify(text, role="User"):
    """Classify `text` as a user message (role='User') or an assistant reply (role='Agent')."""
    messages = [("user", text)] if role == "User" else [("user", "Hospital operations request."),
                                                         ("assistant", text)]
    try:
        raw = get_guard_llm().invoke(messages).content
    except Exception as exc:
        raise GuardUnavailable(str(exc)) from exc
    return parse_verdict(raw)
