"""The agent: system prompt, tools, and one run (memory + live tickets + LLM/tool loop)."""
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from .config import settings
from .db import tickets_snapshot
from .memory import retrieve_memories
from .observability import lf_config
from .tools import ALL_TOOLS

SYSTEM_PROMPT = (
    "You are a concise ticket assistant. The user tells you tasks assigned to them and you track them in a SQL database "
    "using your tools: create tickets for new tasks, update status as they report progress, add notes, and answer "
    "questions about their tickets. The SQL tickets are the source of truth for ticket state - always use tools to "
    "change or read them; never guess ids or status. Memory context (about the user and past conversations) is "
    "background only - use it to personalise answers, but trust the live ticket list over memory if they disagree. "
    "You also have a web_search tool for looking things up. Keep replies short."
)


def build_agent():
    llm = ChatOpenAI(model=settings.model_name)
    return create_agent(model=llm, tools=ALL_TOOLS, system_prompt=SYSTEM_PROMPT)


def _as_text(content) -> str:
    """Message content is normally a string, but can be a list of blocks for some models."""
    if isinstance(content, str):
        return content
    return "".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in content)


def extract_tool_calls(new_messages) -> list[str]:
    """Readable list like ["create_ticket(title='Fix bug', priority='high')"] of the tools used this turn."""
    calls = []
    for m in new_messages:
        for tc in getattr(m, "tool_calls", None) or []:
            args = ", ".join(f"{k}={v!r}" for k, v in tc["args"].items())
            calls.append(f"{tc['name']}({args})")
    return calls


def run_agent(agent, user_msg: str, user_id: str, history=()) -> tuple[str, list[str]]:
    """Memory lookup + live ticket snapshot + one agent run. Returns (reply, tool_calls).

    Call this inside trace_turn(): the LangChain handler nests the LLM and tool calls
    under the current trace automatically.
    """
    memories = retrieve_memories(user_msg, user_id)
    context = (
        f"## What we know about the user (Mem0)\n{memories}\n\n"
        f"## Live tickets (from SQL - source of truth)\n{tickets_snapshot()}"
    )
    messages = [SystemMessage(content=context), *history, HumanMessage(content=user_msg)]
    result = agent.invoke({"messages": messages}, config=lf_config(run_name="ticket-agent"))
    reply = _as_text(result["messages"][-1].content)
    tool_calls = extract_tool_calls(result["messages"][len(messages):])
    return reply, tool_calls
