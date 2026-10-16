"""Architecture tab: guardrails + memory chat layer, then the LangGraph wiring and what spawns when."""
import streamlit as st

from hospital.orchestrator.playbook import PLAYBOOK

CHAT_DOT = """
digraph C {
  rankdir=LR; compound=true; node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=11];
  user [label="User message\\n(chat)", fillcolor="#e5e7eb"];
  csv [label="CSV batch / upload\\n/ queued retry", fillcolor="#e5e7eb"];
  subgraph cluster_guard {
    label="Guardrails (Ollama llama-guard3:1b)"; style="rounded,dashed"; color="#dc2626"; fontname="Helvetica";
    inguard [label="Input guard\\n1 injection patterns\\n2 Llama Guard\\n3 hospital-ops scope", fillcolor="#fecaca"];
    rowguard [label="Batch guard\\nids + timestamps, injection\\nin every field, scope per row", fillcolor="#fecaca"];
    toolguard [label="Tool guard\\nredact poisoned records,\\nvalidate tool args", fillcolor="#fecaca"];
    outguard [label="Output guard\\nLlama Guard + prompt-leak check", fillcolor="#fecaca"];
  }
  refuse [label="Refusal message\\n(blocked / out of scope /\\nguard unreachable)", fillcolor="#fee2e2"];
  subgraph cluster_mem {
    label="Long-term memory (per user, PIN unlock)"; style="rounded,dashed"; color="#2563eb"; fontname="Helvetica";
    pin [label="User ID + PIN\\n(PBKDF2 hash in Postgres)", fillcolor="#dbeafe"];
    mem0 [label="mem0 (hosted)\\nepisodic + semantic", fillcolor="#dbeafe"];
    proc [label="Postgres procedures\\n(procedural)", fillcolor="#dbeafe"];
  }
  learner [label="Procedure learner\\n('always prefer ICU for cardiac')", fillcolor="#bfdbfe"];
  router [label="Intent router\\nquestion / completion / scenario", fillcolor="#bfdbfe"];
  qa [label="Q&A agent\\n(read-only tools + memory context)", fillcolor="#bbf7d0"];
  tools [label="Read tools\\n(CSV store)", fillcolor="#bbf7d0"];
  comp [label="Completion handler\\n(frees resources, retries queue)", fillcolor="#fed7aa"];
  graph [label="Multi-agent graph\\n(orchestrator, agents, arbiter,\\nsynthesizer)", fillcolor="#fde68a"];
  answer [label="Answer / plan\\nto the user", fillcolor="#e9d5ff"];

  user -> inguard;
  inguard -> refuse [label="blocked", color="#dc2626", fontcolor="#dc2626"];
  inguard -> learner [label="allowed"];
  learner -> proc [label="save procedure", style=dashed];
  learner -> router;
  pin -> proc [label="unlocks", style=dotted];
  pin -> mem0 [label="unlocks", style=dotted];
  router -> qa [label="question"];
  router -> comp [label="completion"];
  router -> graph [label="scenario"];
  mem0 -> qa [label="recall", style=dashed];
  proc -> qa [label="procedures", style=dashed];
  qa -> tools; tools -> toolguard [label="records"]; toolguard -> qa [label="sanitised data"];
  qa -> outguard; outguard -> answer;
  csv -> rowguard; rowguard -> graph [label="clean rows"];
  rowguard -> refuse [label="dropped rows", color="#dc2626", fontcolor="#dc2626"];
  comp -> graph [label="retry queued", style=dashed];
  graph -> answer; comp -> answer;
  graph -> mem0 [label="episodic event", style=dashed];
  qa -> mem0 [label="user question", style=dashed];
}
"""

DOT = """
digraph G {
  rankdir=LR; node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=11];
  START [shape=circle, label="", width=0.2, fillcolor=black];
  orchestrator [label="Manager / Orchestrator\\n(triage + priority sort)", fillcolor="#bfdbfe"];
  patient [label="Patient Agent", fillcolor="#bbf7d0"]; doctor [label="Doctor Agent", fillcolor="#bbf7d0"];
  bed [label="Bed Agent", fillcolor="#bbf7d0"]; staff [label="Staff Agent\\n(clerk / housekeeping /\\nhandling dispatchers)", fillcolor="#bbf7d0"];
  arbiter [label="Resource Arbiter\\n(priority, then timestamp)", fillcolor="#fde68a"];
  realloc [label="Reallocation Worker", fillcolor="#fed7aa"]; gap [label="Staffing Gap Resolver", fillcolor="#fed7aa"];
  esc [label="Escalation Agent", fillcolor="#fecaca"]; synth [label="Synthesizer\\n(log + plan)", fillcolor="#e9d5ff"];
  END [shape=doublecircle, label="", width=0.2, fillcolor=black];
  START -> orchestrator;
  orchestrator -> patient [label="Send()", style=dashed]; orchestrator -> doctor [label="Send()", style=dashed];
  orchestrator -> bed [label="Send()", style=dashed]; orchestrator -> staff [label="Send()", style=dashed];
  patient -> arbiter; doctor -> arbiter; bed -> arbiter; staff -> arbiter;
  arbiter -> realloc [label="Send() if ER & no doctor", style=dashed]; arbiter -> gap [label="Send() if no staff", style=dashed];
  realloc -> arbiter; gap -> arbiter;
  arbiter -> esc [label="Send() if unassigned", style=dashed]; arbiter -> synth; esc -> synth; synth -> END;
}
"""


def render_architecture():
    st.subheader("How a request flows")
    st.markdown("**1. Chat layer: guardrails and memory in front of the agents**")
    st.graphviz_chart(CHAT_DOT, width="stretch")
    st.markdown("""
- **Input guard** runs on every chat message before anything else: injection patterns, then
  `llama-guard3:1b` on Ollama, then a hospital-operations scope check. Match scores, maths, general or
  medical questions and mixed requests are refused. If Ollama is down the request is refused (fail closed).
- **Memory** is off until the user unlocks a **User ID + PIN**. **mem0** keeps episodic (shift events) and
  semantic (facts, preferences) memory; standing rules ("always prefer ICU for cardiac") become
  **procedures** in Postgres. Both are screened before saving and added to the Q&A prompt as data,
  not instructions.
- **Batch guard** screens every CSV field, validates ids and timestamps and applies the scope check per row.
- **Tool guard** redacts injected text in patient records before the Q&A model sees it (indirect injection).
- **Output guard** checks answers with Llama Guard and withholds anything that quotes the system prompt.
""")
    st.markdown("**2. Multi-agent graph (scenarios and batches)**")
    st.graphviz_chart(DOT, width="stretch")
    st.markdown("""
- **Manager / Orchestrator** classifies each request with `gpt-4o-mini` (type + priority), sorts emergencies
  first, resolves or reserves a patient id, and emits one `Send()` per agent the request needs.
  Batch size and mix are never hard-coded.
- **Four resource agents** run in parallel and *propose* ranked candidates using their read tools.
- **Resource Arbiter** commits claims through the write tools in priority → timestamp order, so a doctor,
  bed or porter claimed twice goes to the more urgent / earlier request; losers try their next option.
- **Reallocation Worker**, **Staffing Gap Resolver** and **Escalation Agent** are only spawned when needed.
- **Synthesizer** writes the fixed-schema log row per request and the current plan. The finished run is
  saved to mem0 as an episodic memory (when memory is unlocked).
""")
    st.markdown("**Agents spawned per request type**")
    st.table([{"Request type": t, "Send() targets": ", ".join(f"{n} ({task})" for n, task in steps)}
              for t, steps in PLAYBOOK.items()] + [{"Request type": "malformed", "Send() targets": "Escalation Agent"}])
