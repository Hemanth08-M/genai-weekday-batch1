"""Hospital Operations Hub — Streamlit chatbot.

Run from this folder:  streamlit run app.py
"""
import streamlit as st

from ui.architecture_view import render_architecture
from ui.chat_view import render_chat
from ui.report_view import render_report
from ui.session import init_session
from ui.sidebar import render_sidebar

st.set_page_config(page_title="Hospital Ops Hub", page_icon="🏥", layout="wide")
init_session()
render_sidebar()

st.title("🏥 Hospital Operations Hub")
st.caption("Manager agent triages each scenario and spawns Patient, Doctor, Bed and Staff agents on demand "
           "with LangGraph Send(). Ask a question or describe what is happening.")

chat_tab, report_tab, arch_tab = st.tabs(["💬 Operations chat", "📋 Current shift report", "🧭 Architecture"])
with chat_tab:
    render_chat()
with report_tab:
    render_report()
with arch_tab:
    render_architecture()
