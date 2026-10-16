"""Long-term memory with Mem0. Each user_id has a separate memory space.

Both helpers are wrapped in @observe, so memory lookups and saves show up as
named steps inside every trace (the lookup as a `retriever` observation).
"""
import logging
from functools import lru_cache

from langfuse import observe
from mem0 import MemoryClient

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_mem0() -> MemoryClient:
    return MemoryClient()  # reads MEM0_API_KEY from the environment


@observe(name="retrieve-memories", as_type="retriever")
def retrieve_memories(query: str, user_id: str) -> str:
    try:
        results = get_mem0().search(query, filters={"user_id": user_id}, top_k=5)["results"]
    except Exception as exc:  # memory is context, not truth: a failure should not break the turn
        log.warning("memory lookup failed: %s", exc)
        return "(none)"
    return "\n".join(f"- {m['memory']}" for m in results) or "(none yet)"


@observe(name="save-memories")
def save_memories(user_id: str, user_msg: str, tool_calls: list[str], reply: str) -> None:
    assistant_text = reply if not tool_calls else f"(tools used: {'; '.join(tool_calls)})\n{reply}"
    try:
        get_mem0().add(
            [
                {"role": "user", "content": user_msg},
                {"role": "assistant", "content": assistant_text},
            ],
            user_id=user_id,
        )
    except Exception as exc:
        log.warning("saving memory failed: %s", exc)


def list_memories(user_id: str) -> list[str]:
    return [m["memory"] for m in get_mem0().get_all(filters={"user_id": user_id})["results"]]


def delete_memories(user_id: str) -> None:
    get_mem0().delete_all(user_id=user_id)
