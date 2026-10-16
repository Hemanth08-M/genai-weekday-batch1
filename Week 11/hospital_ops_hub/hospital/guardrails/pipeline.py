"""Guardrail pipeline: input (injection -> Llama Guard -> scope), batch rows, output.
Fails closed when the guard model is unreachable."""
import csv
import hashlib
import re
from dataclasses import dataclass
from datetime import datetime

from ..config import GUARDRAILS_ENABLED, STATE_DIR
from .guard_model import CATEGORY_NAMES, GuardUnavailable, classify
from .injection import detect_injection
from .scope import REFUSAL, check_scope, check_scope_many

LOG_FILE = STATE_DIR / "guard_log.csv"
# Llama Guard flags legitimate clinical text under these; they are not attacks on this hub.
CLINICAL_CATEGORIES = {"S6", "S11"}
MAX_INPUT_CHARS = 8000

INJECTION_REFUSAL = ("🛡️ Blocked: this message looks like an attempt to override the assistant's "
                     "instructions or misuse its tools. Nothing was processed.")
UNSAFE_REFUSAL = "🛡️ Blocked: this message was flagged as unsafe ({cats}). Nothing was processed."
UNAVAILABLE_REFUSAL = ("🛡️ The safety service (Ollama / llama-guard3:1b) is unreachable, so the request "
                       "was not processed. Start Ollama or set GUARDRAILS_ENABLED=false.")
EMPTY_REFUSAL = "Please type a request or question about hospital operations."
OUTPUT_REFUSAL = "🛡️ The response was withheld by the output safety check."

REQUEST_ID_OK = re.compile(r"^[A-Za-z0-9_.\-]{0,40}$")
TIMESTAMP_OK = re.compile(r"^[0-9T:\-+.Z/ ]{0,32}$")
BATCH_FIELDS = ("request_id", "timestamp", "description", "location", "reported_by")
MIN_WORDS_FOR_SCOPE = 4          # shorter rows (e.g. "???? urgent") go to triage as malformed

_SECRETS = []                    # prompt fragments that must never appear in an answer


@dataclass
class Decision:
    allowed: bool = True
    reason: str = ""
    message: str = ""   # refusal text for the user when blocked


def register_secret(text):
    """Register a system prompt so check_output can withhold replies that quote it."""
    for sentence in re.split(r"(?<=[.:?!])\s+|\n+", text):
        s = " ".join(sentence.lower().split())
        if len(s) >= 30 and s not in _SECRETS:
            _SECRETS.append(s)


def leaks_prompt(text):
    flat = " ".join(str(text).lower().split())
    return any(s in flat for s in _SECRETS)


def _redact(text, limit=80):
    """Log-safe snippet: digits masked, short, with a hash so repeats can be correlated."""
    flat = " ".join(str(text).split())
    digest = hashlib.sha1(flat.encode("utf-8")).hexdigest()[:8]
    return f"{re.sub(r'\d', '#', flat[:limit])} [sha1:{digest} len:{len(flat)}]"


def log_block(stage, user_id, reason, text):
    """Append one blocked event to data/state/guard_log.csv (text is masked and truncated)."""
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        new = not LOG_FILE.exists()
        with LOG_FILE.open("a", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            if new:
                writer.writerow(["timestamp", "stage", "user_id", "reason", "text"])
            writer.writerow([datetime.now().isoformat(timespec="seconds"), stage, user_id, reason,
                             _redact(text)])
    except OSError:
        pass


def screen_text(text, role="User", ignore=frozenset(), use_guard=True):
    """Injection heuristics + Llama Guard (skipped when use_guard=False). Returns a Decision."""
    hits = detect_injection(text)
    if hits:
        return Decision(False, "injection:" + ",".join(hits), INJECTION_REFUSAL)
    if not use_guard:
        return Decision()
    try:
        verdict = classify(text[:MAX_INPUT_CHARS], role)
    except GuardUnavailable as exc:
        return Decision(False, f"guard_unavailable:{exc}", UNAVAILABLE_REFUSAL)
    cats = [c for c in verdict.categories if c not in ignore]
    if not verdict.safe and cats:
        names = ", ".join(f"{c} {CATEGORY_NAMES.get(c, '')}".strip() for c in cats)
        return Decision(False, "llama_guard:" + ",".join(cats), UNSAFE_REFUSAL.format(cats=names))
    return Decision()


def check_input(text, user_id="anonymous"):
    """Gate a chat message: injection/safety first, then the hospital-operations scope."""
    if not GUARDRAILS_ENABLED:
        return Decision()
    if not str(text or "").strip():
        return Decision(False, "empty", EMPTY_REFUSAL)
    decision = screen_text(text, "User", ignore=CLINICAL_CATEGORIES)
    if not decision.allowed:
        log_block("input", user_id, decision.reason, text)
        return decision
    scope = check_scope(text)
    if not scope.in_scope:
        log_block("scope", user_id, scope.reason, text)
        return Decision(False, "out_of_scope:" + scope.reason, REFUSAL)
    return Decision()


def check_batch_rows(rows, user_id="anonymous", scope=True):
    """Screen CSV / scenario rows: format of ids and timestamps, injection in EVERY field,
    Llama Guard, and (optionally) hospital-ops scope per description.
    Returns (clean_rows, blocked) where blocked is a list of {"request_id", "reason"}."""
    if not GUARDRAILS_ENABLED:
        return list(rows), []
    clean, blocked = [], []

    def drop(row, reason, text):
        blocked.append({"request_id": str(row.get("request_id") or "?")[:40], "reason": reason})
        log_block("batch_row", user_id, reason, text)

    survivors = []
    for row in rows:
        values = {k: str(row.get(k) or "") for k in BATCH_FIELDS}
        if not REQUEST_ID_OK.match(values["request_id"]):
            drop(row, "invalid_request_id", values["request_id"])
            continue
        if not TIMESTAMP_OK.match(values["timestamp"]):
            drop(row, "invalid_timestamp", values["timestamp"])
            continue
        text = " \n".join(values[k] for k in ("description", "location", "reported_by"))
        # very short / junk rows ("???? urgent") only get the pattern check: the 1B guard model
        # mislabels them and triage already marks them malformed
        words = len(re.findall(r"[A-Za-z]{2,}", text))
        decision = (screen_text(text, "User", ignore=CLINICAL_CATEGORIES, use_guard=words >= MIN_WORDS_FOR_SCOPE)
                    if text.strip() else Decision())
        if decision.allowed:
            survivors.append((row, values["description"]))
        else:
            drop(row, decision.reason, text)

    to_check = [(i, d) for i, (_, d) in enumerate(survivors) if scope and len(re.findall(r"[A-Za-z]{2,}", d)) >= MIN_WORDS_FOR_SCOPE]
    verdicts = dict(zip((i for i, _ in to_check), check_scope_many(d for _, d in to_check)))
    for i, (row, desc) in enumerate(survivors):
        verdict = verdicts.get(i)
        if verdict is not None and not verdict.in_scope:
            drop(row, "out_of_scope:" + verdict.reason, desc)
        else:
            clean.append(row)
    return clean, blocked


def check_output(text, user_id="anonymous"):
    """Screen an assistant reply before it is shown. Returns the text or a refusal."""
    if not GUARDRAILS_ENABLED or not text:
        return text
    if leaks_prompt(text):
        log_block("output", user_id, "system_prompt_leak", text)
        return OUTPUT_REFUSAL
    decision = screen_text(text, "Agent", ignore=CLINICAL_CATEGORIES)
    if decision.allowed:
        return text
    log_block("output", user_id, decision.reason, text)
    return OUTPUT_REFUSAL
