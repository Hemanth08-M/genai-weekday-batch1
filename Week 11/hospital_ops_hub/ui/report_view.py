"""Current Shift Report tab: live CSVs of patients, doctors, beds, staff and the shift logs."""
from datetime import datetime

import streamlit as st

from hospital.reporting.shift_log import get_shift_log
from hospital.reporting.shift_report import (csv_bytes, current_tables, end_shift, metrics,
                                             summarize_shift, zip_bytes)

TABS = [("patients", "🧑 Patients"), ("doctors", "🩺 Doctors"), ("beds", "🛏️ Beds"), ("staff", "👷 Staff"),
        ("request_log", "📝 Request log"), ("worker_trace", "🔗 Agent trace"), ("escalations", "🚨 Escalations")]


def _highlight_status(value):
    colors = {"free": "#d1fae5", "available": "#d1fae5", "assigned": "#d1fae5", "admitted": "#dbeafe",
              "occupied": "#fee2e2", "busy": "#fee2e2", "escalated": "#fee2e2",
              "waiting": "#fef3c7", "queued": "#fef3c7", "completed": "#e5e7eb", "retried": "#e5e7eb"}
    color = colors.get(value)
    return f"background-color: {color}; color: #111" if color else ""


def render_report():
    log = get_shift_log()
    tables = current_tables()
    stamp = datetime.now().strftime("%Y%m%d-%H%M")

    head, actions = st.columns([3, 2])
    head.subheader(f"Shift {log.shift_id} — current report")
    head.caption(f"Shift started {log.meta['started_at']}. Resource lists are live; logs cover this shift.")
    summary = summarize_shift(tables)
    actions.download_button("⬇️ Download full report (.zip)", zip_bytes(tables, summary),
                            file_name=f"shift_{log.shift_id:03d}_{stamp}.zip", mime="application/zip",
                            width="stretch")
    if actions.button("🏁 End shift & start new one", width="stretch",
                      help="Archives this report to reports/ and starts a fresh shift log. Resources carry over."):
        folder = end_shift()
        st.success(f"Shift archived to {folder.name}. New shift {get_shift_log().shift_id} started.")
        st.rerun()

    for col, (label, value) in zip(st.columns(5), metrics(tables).items()):
        col.metric(label, value)

    req = tables["request_log"]
    if not req.empty:
        badges = [("✅ Assigned", "assigned"), ("⏳ Queued", "queued"), ("🚨 Escalated", "escalated"),
                  ("✔️ Completed", "completed"), ("🔁 Retried", "retried")]
        for col, (label, status) in zip(st.columns(len(badges)), badges):
            col.metric(label, int((req["status"] == status).sum()))
        st.caption("Queued = routine work waiting for a free resource. Report finished work in chat "
                   "(e.g. *R03 done*) to release its staff; queued items are then retried automatically.")

    for tab, (name, label) in zip(st.tabs([label for _, label in TABS]), TABS):
        with tab:
            df = tables[name]
            status_cols = [c for c in ("status",) if c in df.columns]
            styled = df.style.map(_highlight_status, subset=status_cols) if status_cols and not df.empty else df
            st.dataframe(styled, hide_index=True, width="stretch")
            st.download_button(f"⬇️ {name}.csv", csv_bytes(df), file_name=f"{name}_shift{log.shift_id}_{stamp}.csv",
                               mime="text/csv", key=f"dl_{name}")

    with st.expander("Shift summary (markdown)"):
        st.markdown(summary)
