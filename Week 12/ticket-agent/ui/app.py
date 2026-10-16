"""Streamlit chat UI. It only talks to the API over HTTP - it never imports LangChain, Mem0 or the DB code.

NOTE: the HTTP calls below run inside the *ui container* (Streamlit's server process), not in your browser.
That is why API_URL can be the Compose service name (http://api:8000): your browser never contacts the API.
"""
import os
import uuid

import httpx
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000").rstrip("/")
USERS = ["alice", "bob", "carol"]
CHAT_TIMEOUT = 180  # agent turns involve several LLM calls


st.set_page_config(page_title="Ticket Agent", page_icon="🎫", layout="wide")


def api_get(path: str):
    r = httpx.get(f"{API_URL}{path}", timeout=30)
    r.raise_for_status()
    return r.json()


def api_chat(user_id: str, session_id: str, message: str) -> dict:
    r = httpx.post(
        f"{API_URL}/chat",
        json={"user_id": user_id, "session_id": session_id, "message": message},
        timeout=CHAT_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def new_session() -> None:
    # Streamlit re-runs this whole script on every interaction, so anything that must survive lives in session_state.
    st.session_state.session_id = f"ui-{uuid.uuid4().hex[:6]}"
    st.session_state.messages = []


def render_message(msg: dict) -> None:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant":
            with st.expander("Details"):
                tools = msg.get("tool_calls") or []
                st.code("\n".join(tools) if tools else "No tools used", language="text")
                if msg.get("trace_url"):
                    st.markdown(f"[Open this turn's trace in Langfuse]({msg['trace_url']})")


# ------------------------------------------------------------------ state
if "session_id" not in st.session_state:
    new_session()

# ------------------------------------------------------------------ sidebar
st.sidebar.title("🎫 Ticket Agent")
user_id = st.sidebar.selectbox("User", USERS)
if st.session_state.get("last_user") not in (None, user_id):
    new_session()                                  # switching user starts a fresh conversation
st.session_state.last_user = user_id

if st.sidebar.button("New session"):
    new_session()
    st.rerun()
st.sidebar.caption(f"session: `{st.session_state.session_id}`")

st.sidebar.subheader("Tickets")
try:
    tickets = api_get("/tickets")
    if tickets:
        st.sidebar.dataframe(tickets, hide_index=True)
    else:
        st.sidebar.write("(no tickets)")
except httpx.HTTPError as exc:
    st.sidebar.error(f"Cannot load tickets: {exc}")

if st.sidebar.button("Show memories"):
    try:
        mems = api_get(f"/memories/{user_id}")["memories"]
        st.sidebar.write("\n".join(f"- {m}" for m in mems) if mems else "(none yet)")
    except httpx.HTTPError as exc:
        st.sidebar.error(f"Cannot load memories: {exc}")

# ------------------------------------------------------------------ chat
st.header("Chat")
for msg in st.session_state.messages:
    render_message(msg)

prompt = st.chat_input("Tell me about your tasks, or ask about your tickets...")
if prompt:
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                data = api_chat(user_id, st.session_state.session_id, prompt)
            except httpx.HTTPError as exc:
                st.error(f"Request failed: {exc}")
                data = None
    if data:
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.session_state.messages.append({
            "role": "assistant",
            "content": data["reply"],
            "tool_calls": data.get("tool_calls", []),
            "trace_url": data.get("trace_url"),
        })
        st.rerun()   # redraw so the sidebar ticket table reflects what the agent just changed
