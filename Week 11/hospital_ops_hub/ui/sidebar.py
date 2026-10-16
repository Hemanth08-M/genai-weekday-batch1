"""Sidebar: simulation clock, request batches, upload, retry queue, reset."""
from datetime import datetime

import streamlit as st

from hospital.chat.parser import parse_csv_text
from hospital.config import ENV_FILE, MODEL_NAME, REQUESTS_DIR
from hospital.llm import llm_available
from hospital.memory import delete_all_procedures, forget_all, unlock
from hospital.memory.auth import MIN_PIN
from hospital.operations.completion import queued_requests
from hospital.reporting.shift_log import get_shift_log
from hospital.store import get_store

from .chat_view import run_batch
from .session import current_user


UNLOCK_MESSAGES = {
    "bad_user": "Enter a user ID (max 64 characters).",
    "weak_pin": f"PIN must be at least {MIN_PIN} characters.",
    "denied": "Wrong PIN for this user ID.",
    "unavailable": "Postgres is unreachable, so memory stays off.",
}


def _memory_login():
    """User ID + PIN: memory (mem0 and saved procedures) is only used after the PIN is verified."""
    st.text_input("👤 User ID", key="user_id", help="Memory is kept per user ID.")
    st.text_input("🔑 PIN", key="user_pin", type="password",
                  help="First use of an ID registers this PIN; later uses must match.")
    user = current_user()
    if user:
        st.success(f"Memory on for {user}", icon="🧠")
        if st.button("🗑️ Forget my memory", width="stretch",
                     help="Deletes your mem0 memories and saved procedures"):
            forget_all(user)
            delete_all_procedures(user)
            st.toast("Memory cleared")
        return
    if st.button("🔓 Unlock memory", width="stretch"):
        result = unlock((st.session_state.user_id or "").strip(), st.session_state.get("user_pin"))
        if result in ("ok", "registered"):
            st.session_state.unlocked_user = st.session_state.user_id.strip()
            st.rerun()
        st.error(UNLOCK_MESSAGES.get(result, "Could not unlock memory."))
    else:
        st.caption("Memory is off until you unlock it.")


def _clock():
    st.markdown("**🕒 Simulation clock**")
    st.caption("Chat scenarios are timestamped with this (shift-end rule depends on it).")
    clock = st.session_state.sim_clock
    d = st.date_input("Date", clock.date(), label_visibility="collapsed")
    t = st.time_input("Time", clock.time(), step=60, label_visibility="collapsed")
    st.session_state.sim_clock = datetime.combine(d, t)


def _batches():
    st.markdown("**📦 Test request batches**")
    for path in sorted(REQUESTS_DIR.glob("*.csv")):
        rows = parse_csv_text(path.read_text(encoding="utf-8"))
        if st.button(f"Run {path.stem} ({len(rows)})", key=f"batch_{path.stem}", width="stretch"):
            run_batch(rows, f"▶️ Run batch **{path.name}** ({len(rows)} requests)")
            st.rerun()
    upload = st.file_uploader("Upload a requests CSV", type="csv")
    if upload is not None and st.button("Run uploaded batch", width="stretch"):
        rows = parse_csv_text(upload.getvalue().decode("utf-8"))
        run_batch(rows, f"▶️ Run uploaded batch **{upload.name}** ({len(rows)} requests)")
        st.rerun()


def _retry_queue():
    queued = queued_requests()
    if st.button(f"🔁 Retry queued requests ({len(queued)})", disabled=not queued, width="stretch"):
        stamp = st.session_state.sim_clock.isoformat(timespec="minutes")
        rows = [{"request_id": f"{r['request_id'].split('-retry')[0]}-retry", "timestamp": stamp,
                 "description": r["description"], "location": "", "reported_by": "queue",
                 "retry_of": r["request_id"]} for r in queued]
        run_batch(rows, f"🔁 Retry {len(rows)} queued request(s) at {stamp}")
        st.rerun()


def render_sidebar():
    with st.sidebar:
        st.markdown("## 🏥 Hospital Ops Hub")
        if llm_available():
            st.success(f"LLM: {MODEL_NAME}", icon="✅")
        else:
            st.warning("No OPENAI_API_KEY found — triage falls back to keyword rules.", icon="⚠️")
        if ENV_FILE:
            st.caption(f".env loaded from `{ENV_FILE.parent.name}/`")
        _memory_login()
        _clock()
        st.divider()
        _batches()
        st.divider()
        _retry_queue()
        if st.button("♻️ Reset to seed data", width="stretch",
                     help="Restore patients/doctors/beds/staff from seed CSVs and start shift 1"):
            get_store().reset()
            get_shift_log().reset()
            st.session_state.messages = []
            st.session_state.chat_counter = 1
            st.rerun()
        if st.button("🧹 Clear chat", width="stretch"):
            st.session_state.messages = []
            st.rerun()
