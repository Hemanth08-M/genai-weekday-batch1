"""HTTP API for the ticket agent.

    POST /chat                 one chat turn  (= one Langfuse trace)
    GET  /tickets              current tickets
    GET  /memories/{user_id}   what Mem0 stored for a user
    GET  /health               used by Docker Compose's healthcheck

Run with a SINGLE worker: conversation history is kept in this process's memory.
"""
import logging
import re
import threading
from collections import OrderedDict
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from ticket_agent import db, memory, observability
from ticket_agent.agent import build_agent
from ticket_agent.chat import ChatSession
from ticket_agent.config import check_env

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
logging.getLogger("ticket_agent").setLevel(logging.INFO)
log = logging.getLogger("api")

ID_PATTERN = r"^[A-Za-z0-9_.-]{1,64}$"
MAX_SESSIONS = 500


class SessionStore:
    """In-memory conversations keyed by (user_id, session_id); least recently used are evicted."""

    def __init__(self, agent, max_sessions: int = MAX_SESSIONS):
        self._agent = agent
        self._max = max_sessions
        self._sessions: OrderedDict[tuple[str, str], ChatSession] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, user_id: str, session_id: str) -> ChatSession:
        key = (user_id, session_id)
        with self._lock:
            session = self._sessions.get(key)
            if session is None:
                session = ChatSession(user_id, session_id, tags=["ticket-agent", "api"], agent=self._agent)
                self._sessions[key] = session
            self._sessions.move_to_end(key)
            while len(self._sessions) > self._max:
                self._sessions.popitem(last=False)
            return session


@asynccontextmanager
async def lifespan(app: FastAPI):
    check_env()
    observability.init_langfuse()       # create the Langfuse client once, with masking
    db.init_db()                        # wait for Postgres, create tables
    app.state.sessions = SessionStore(build_agent())
    log.info("API ready")
    yield
    observability.shutdown()            # flush any buffered traces


app = FastAPI(title="Ticket Agent API", lifespan=lifespan)


class ChatRequest(BaseModel):
    user_id: str = Field(pattern=ID_PATTERN, description="Shows on Langfuse's Users page; separates Mem0 memories")
    session_id: str = Field(pattern=ID_PATTERN, description="One conversation; shows on Langfuse's Sessions page")
    message: str = Field(min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    reply: str
    tool_calls: list[str]
    trace_url: str | None
    session_id: str


@app.get("/health")
def health():
    try:
        db.ping()
    except Exception:
        raise HTTPException(status_code=503, detail="database unavailable")
    return {"status": "ok"}


# Plain `def` (not async): FastAPI runs these in a thread pool, so slow LLM calls don't block the server.
@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    session = app.state.sessions.get(req.user_id, req.session_id)
    try:
        result = session.say(req.message)
    except Exception:
        # The failed turn is already marked ERROR in Langfuse; don't leak internals to the client.
        log.exception("chat turn failed (user=%s session=%s)", req.user_id, req.session_id)
        raise HTTPException(status_code=500, detail="The agent failed on this request. Check the Langfuse trace / API logs.")
    return ChatResponse(
        reply=result.reply,
        tool_calls=result.tool_calls,
        trace_url=result.trace_url or None,
        session_id=req.session_id,
    )


@app.get("/tickets")
def tickets():
    return db.fetch_tickets()


@app.get("/memories/{user_id}")
def memories(user_id: str):
    if not re.fullmatch(ID_PATTERN, user_id):
        raise HTTPException(status_code=422, detail="invalid user_id")
    try:
        return {"user_id": user_id, "memories": memory.list_memories(user_id)}
    except Exception:
        log.exception("memory listing failed")
        raise HTTPException(status_code=502, detail="Memory service unavailable")
