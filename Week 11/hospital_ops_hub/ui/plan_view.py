"""Render one graph run as the 'current plan' inside the chat."""
import pandas as pd
import streamlit as st

from hospital.models import LOG_COLUMNS

PRIORITY_BADGE = {"emergency": "🔴 emergency", "urgent": "🟠 urgent", "routine": "🟢 routine"}
STATUS_BADGE = {"assigned": "✅ assigned", "queued": "⏳ queued", "escalated": "🚨 escalated",
                "completed": "✔️ completed", "retried": "🔁 retried"}


def _spawned(trace, request_id):
    """Agents/workers that ran for this request, in order, from the trace."""
    names = [t["worker"] for t in trace
             if t["request_id"] == request_id and t["event"] in ("proposed", "escalated")]
    return list(dict.fromkeys(names))


def render_request_card(row, trace):
    with st.container(border=True):
        st.markdown(f"**{row['request_id']}** · `{row['type']}` · {PRIORITY_BADGE.get(row['priority'], row['priority'])}"
                    f" · {STATUS_BADGE.get(row['status'], row['status'])} · ⏱ {row['time_taken']}s")
        if row.get("description"):
            st.caption(row["description"])
        cols = st.columns(4)
        for col, key, icon in zip(cols, ("patient", "doctor", "bed", "staff"), ("🧑", "🩺", "🛏️", "👷")):
            col.markdown(f"{icon} **{key.title()}**  \n{row[key] or '—'}")
        spawned = _spawned(trace, row["request_id"])
        st.markdown("**Spawned via Send():** " + (" → ".join(spawned) if spawned else "none (no agent needed)"))
        if row["reason"]:
            with st.expander("Reasoning"):
                for part in row["reason"].split("; "):
                    st.markdown(f"- {part}")


def render_plan(result):
    rows, trace = result.get("log_rows", []), result.get("trace", [])
    st.markdown("### 🗺️ Current plan")
    st.markdown(result.get("plan_summary", ""))
    if rows:
        st.markdown("### Per-request outcome")
        for row in rows:
            render_request_card(row, trace)
        with st.expander("Fixed-schema log rows"):
            st.dataframe(pd.DataFrame(rows)[LOG_COLUMNS], hide_index=True, width="stretch")
    with st.expander(f"Agent trace ({len(trace)} events)"):
        st.dataframe(pd.DataFrame(trace), hide_index=True, width="stretch")
