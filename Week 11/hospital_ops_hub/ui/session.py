"""Streamlit session helpers: cached service, simulation clock, chat history."""
from datetime import datetime, timedelta

import streamlit as st

from hospital.chat.service import HospitalChatService
from hospital.config import DEFAULT_SIM_CLOCK, DEFAULT_USER_ID
from hospital.utils import parse_ts


@st.cache_resource
def _cached_service():
    return HospitalChatService()


def get_service():
    service = _cached_service()
    # After a code edit Streamlit reloads the module, so a cached instance of the old class
    # no longer matches; rebuild it instead of calling stale methods.
    if not isinstance(service, HospitalChatService):
        _cached_service.clear()
        service = _cached_service()
    return service


def init_session():
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("sim_clock", datetime.fromisoformat(DEFAULT_SIM_CLOCK))
    st.session_state.setdefault("chat_counter", 1)
    st.session_state.setdefault("user_id", DEFAULT_USER_ID)
    st.session_state.setdefault("unlocked_user", None)


def current_user():
    """The user ID whose memory is unlocked (PIN verified), or None, which turns memory off."""
    typed = (st.session_state.get("user_id") or "").strip()
    return typed if typed and typed == st.session_state.get("unlocked_user") else None


def advance_clock(rows):
    """Move the simulation clock past the latest request so later scenarios follow on."""
    stamps = [parse_ts(r.get("timestamp")) for r in rows]
    stamps = [s for s in stamps if s]
    if stamps:
        st.session_state.sim_clock = max(stamps) + timedelta(minutes=1)


def add_message(role, content=None, result=None, label=None):
    st.session_state.messages.append({"role": role, "content": content, "result": result, "label": label})
