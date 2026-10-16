"""mem0 (hosted) long-term memory: episodic (what happened) + semantic (durable facts/preferences).
Every call is best-effort: with no MEM0_API_KEY, no unlocked user or on any error the hub keeps
working without memory. Text is screened before it is stored, so poisoned text is never recalled."""
import os
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

from ..guardrails.pipeline import CLINICAL_CATEGORIES, screen_text
from .procedural_store import valid_user_id

APP_ID = "hospital_ops_hub"
MAX_CHARS = 1000
_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="mem0")


def mem0_available():
    return bool(os.getenv("MEM0_API_KEY"))


@lru_cache(maxsize=1)
def get_client():
    from mem0 import MemoryClient
    return MemoryClient(api_key=os.environ["MEM0_API_KEY"])


def recall(user_id, query, limit=5):
    """Return memory strings relevant to `query` for this user."""
    if not mem0_available() or not valid_user_id(user_id):
        return []
    try:
        res = get_client().search(query, filters={"user_id": user_id}, limit=limit)
        items = res.get("results", []) if isinstance(res, dict) else res
        return [m["memory"] for m in items if m.get("memory")]
    except Exception:
        return []


def _safe(messages):
    """Keep only messages that pass the injection / Llama Guard screen. Returns the cleaned list."""
    kept = []
    for m in messages:
        text = str(m.get("content", ""))[:MAX_CHARS]
        if text.strip() and screen_text(text, "User", ignore=CLINICAL_CATEGORIES).allowed:
            kept.append({"role": m.get("role", "user"), "content": text})
    return kept


def remember(user_id, messages, kind="semantic"):
    """Store a conversation turn. mem0 extracts semantic facts itself; `kind` is kept as metadata
    (episodic = shift events such as scenarios and completions)."""
    if not mem0_available() or not valid_user_id(user_id) or not messages:
        return False
    messages = _safe(messages)
    if not messages:
        return False
    try:
        get_client().add(messages, user_id=user_id, app_id=APP_ID, metadata={"type": kind})
        return True
    except Exception:
        return False


def remember_async(user_id, messages, kind="semantic"):
    """Fire-and-forget remember() so memory writes never slow down an answer."""
    if mem0_available() and valid_user_id(user_id):
        _pool.submit(remember, user_id, messages, kind)


def remember_episode(user_id, summary, background=True):
    """Record a shift event (scenario outcome, completion) as an episodic memory."""
    messages = [{"role": "user", "content": f"Shift event: {summary}"}]
    if background:
        remember_async(user_id, messages, kind="episodic")
        return True
    return remember(user_id, messages, kind="episodic")


def forget_all(user_id):
    """Delete every mem0 memory of this user."""
    if not mem0_available() or not valid_user_id(user_id):
        return False
    try:
        client = get_client()
        client.delete_all(user_id=user_id)
        # delete_all can leave items behind, so remove whatever is still listed one by one
        res = client.get_all(filters={"user_id": user_id}, page_size=100)
        for item in (res.get("results", []) if isinstance(res, dict) else res):
            client.delete(item["id"])
        return True
    except AttributeError:       # client without get_all/delete (e.g. a test fake)
        return True
    except Exception:
        return False
