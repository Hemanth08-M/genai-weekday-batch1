"""ChatSession: one conversation = one Langfuse session."""
import threading
import uuid
from dataclasses import dataclass, field

from langchain_core.messages import AIMessage, HumanMessage

from .agent import build_agent, run_agent
from .config import settings
from .memory import save_memories
from .observability import trace_turn


@dataclass
class ChatResult:
    reply: str
    tool_calls: list[str] = field(default_factory=list)
    trace_url: str = ""


class ChatSession:
    """Fixed user_id + session_id, plus a short message history so 'that ticket' makes sense.

    The same session_id goes on every turn - that is all Langfuse needs to group
    the turns into one thread on the Sessions page.
    """

    def __init__(self, user_id: str, session_id: str | None = None, name: str = "chat",
                 tags: list[str] | None = None, agent=None):
        self.user_id = user_id
        self.session_id = session_id or f"{name}-{uuid.uuid4().hex[:6]}"
        self.tags = tags or ["ticket-agent"]
        self.agent = agent or build_agent()
        self.history: list = []
        self._lock = threading.Lock()   # two requests for the same conversation must not interleave

    def say(self, user_msg: str) -> ChatResult:
        with self._lock:
            with trace_turn(user_msg=user_msg, user_id=self.user_id, session_id=self.session_id, tags=self.tags) as turn:
                reply, tool_calls = run_agent(self.agent, user_msg, self.user_id, self.history)
                save_memories(self.user_id, user_msg, tool_calls, reply)
                turn.reply, turn.tool_calls = reply, tool_calls

            # Only reached when the turn succeeded; a failed turn never pollutes the history.
            self.history = (self.history + [HumanMessage(content=user_msg), AIMessage(content=reply)])[
                -2 * settings.short_term_turns :
            ]
        return ChatResult(reply=reply, tool_calls=tool_calls, trace_url=turn.trace_url)
