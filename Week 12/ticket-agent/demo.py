"""Scripted conversations for three users, to fill the Tracing / Sessions / Users pages in Langfuse.
Talks to the running API over HTTP.

    docker compose exec api python demo.py          # from inside the api container
    API_URL=http://localhost:8000 python demo.py    # or from your machine (needs httpx)
"""
import os
import uuid

import httpx

API_URL = os.getenv("API_URL", "http://localhost:8000").rstrip("/")

SCRIPTS = {
    # (user_id, session name): messages
    ("alice", "alice-sprint"): [
        "Hi! I'm on the payments team (alice@example.com) and I prefer short answers.",   # the email is masked in Langfuse
        "I've been assigned to investigate the intermittent 502 errors on the payments gateway, high priority.",
        "Search the web: what usually causes 502 errors behind a load balancer?",
        "Add a note to that ticket with the top cause you found.",
        "Mark it in progress.",
    ],
    ("bob", "bob-docs"): [
        "Mark the refund docs ticket as blocked, waiting on the API spec.",
        "What is the status of my tickets?",
    ],
    ("carol", "carol-triage"): [
        "What's on my plate right now?",
        "Close the psycopg upgrade ticket.",
    ],
}


def main() -> None:
    with httpx.Client(base_url=API_URL, timeout=180) as http:
        for (user, name), messages in SCRIPTS.items():
            session_id = f"{name}-{uuid.uuid4().hex[:6]}"
            print(f"\n=== {user} / {session_id} ===")
            for msg in messages:
                print(f"[{user}] You: {msg}")
                r = http.post("/chat", json={"user_id": user, "session_id": session_id, "message": msg})
                r.raise_for_status()
                data = r.json()
                for call in data["tool_calls"]:
                    print(f"   [tool] {call}")
                print(f"Agent: {data['reply']}")
                if data.get("trace_url"):
                    print(f"   [trace] {data['trace_url']}\n")


if __name__ == "__main__":
    main()
