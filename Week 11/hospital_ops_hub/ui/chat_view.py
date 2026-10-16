"""Chat tab: scenarios go to the multi-agent graph, questions go to the read-only Q&A agent."""
import streamlit as st

from .plan_view import render_plan
from .session import add_message, advance_clock, current_user, get_service

EXAMPLES = [
    "Ambulance arrival: man around 60, severe chest pain and sweating, needs cardiologist and ER bed immediately",
    "Blood spill in ER corridor, possible contamination, needs specialized cleaning",
    "Post-op patient Rahul Dev, 55, needs an ICU bed urgently. ICU may be full",
    "How many free beds are there in each ward?",
]


def _completion_message(results, retry_rows):
    lines = ["### ✔️ Work completion"]
    for r in results:
        icon = "✅" if r["ok"] else "⚠️"
        lines.append(f"- {icon} **{r['request_id']}**: {r['message']}")
    if not any(r.get("released") for r in results):
        lines.append("\nNothing was released, so queued requests were not retried.")
    elif not retry_rows:
        lines.append("\nResources freed. No queued requests were waiting.")
    else:
        lines.append(f"\nResources freed → re-running {len(retry_rows)} queued request(s):")
    return "\n".join(lines)


def run_batch(rows, label):
    """Shared by the chat input and the sidebar batch buttons."""
    add_message("user", content=label)
    with st.spinner(f"Orchestrator triaging {len(rows)} request(s) and spawning agents..."):
        try:
            result = get_service().run_requests(rows, current_user())
        except Exception as exc:
            add_message("assistant", content=f"⚠️ Run failed: {exc}")
            return
    advance_clock(rows)
    _add_result(result)


def _add_result(result):
    """Show a graph result, plus a notice for any rows the guardrails dropped."""
    blocked = result.get("guard_blocked") or []
    if blocked:
        lines = ["### 🛡️ Guardrails blocked request(s)"]
        lines += [f"- **{b['request_id']}**: {b['reason']}" for b in blocked]
        add_message("assistant", content="\n".join(lines))
    add_message("assistant", result=result)


def _handle(text):
    service = get_service()
    user_id = current_user()
    add_message("user", content=text)
    with st.spinner("Thinking..."):
        try:
            decision = service.screen(text, user_id)
            if not decision.allowed:
                add_message("assistant", content=decision.message)
                return
            procedure = service.learn(text, user_id)
            if procedure:
                add_message("assistant", content=f"📌 Saved procedure **{procedure}** to your memory.")
                return
            intent = service.classify_intent(text)
            if intent.intent == "question":
                add_message("assistant", content=service.answer_question(text, user_id, screened=True))
                return
            if intent.intent == "completion":
                results, retry_rows, retry_state = service.complete(intent.request_ids,
                                                                    st.session_state.sim_clock, user_id)
                add_message("assistant", content=_completion_message(results, retry_rows))
                if retry_state is not None:
                    _add_result(retry_state)
                return
            rows, result = service.run_scenario_text(text, st.session_state.sim_clock,
                                                     st.session_state.chat_counter, user_id,
                                                     screened=True)
        except Exception as exc:
            add_message("assistant", content=f"⚠️ Could not process that: {exc}")
            return
    st.session_state.chat_counter += len(rows)
    advance_clock(rows)
    _add_result(result)


def render_history():
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"], avatar="🧑‍⚕️" if msg["role"] == "user" else "🏥"):
            if msg.get("result") is not None:
                render_plan(msg["result"])
            else:
                st.markdown(msg["content"])


def render_chat():
    if not st.session_state.messages:
        st.info("Describe a situation (one per line), paste rows from a request batch CSV, "
                "ask a question about current beds, doctors, patients or staff, "
                "or report finished work, e.g. **R03 done** (frees its staff and retries queued work).")
        cols = st.columns(len(EXAMPLES))
        for col, example in zip(cols, EXAMPLES):
            if col.button(example[:60] + "…", key=f"ex_{example[:20]}", width="stretch"):
                _handle(example)
                st.rerun()
    render_history()
    text = st.chat_input("e.g. Young woman unconscious with seizures, needs neurologist now")
    if text:
        _handle(text)
        st.rerun()
