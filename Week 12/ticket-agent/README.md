# Ticket Agent: FastAPI + Streamlit + Postgres, traced with Langfuse

A ticket-support agent (LangChain) that tracks tickets in Postgres, remembers users with Mem0, can search the web,
and sends a full trace of every chat turn to Langfuse. Three containers, one Compose project.

```
Browser --> ui (Streamlit :8501) --> api (FastAPI :8000) --> postgres (:5432)
                                        |
                                        +--> OpenAI, Mem0, Langfuse (external, over the internet)
```

| Service      | Image                          | Published port                                   |
| ------------ | ------------------------------ | ------------------------------------------------ |
| `postgres` | official `postgres:16`       | 5433 (optional, for debugging from your machine) |
| `api`      | built from `./Dockerfile`    | 8000 (Swagger UI at `/docs`)                   |
| `ui`       | built from `./ui/Dockerfile` | 8501                                             |

Containers reach each other by **service name** on Compose's private network (`postgres:5432`, `http://api:8000`).
`localhost` inside a container means that container itself.

## Quick start

```bash
cp .env.example .env          # then fill in the four keys
docker compose up --build
```

Open the UI at http://localhost:8501 and the API docs at http://localhost:8000/docs.

> If you still have the old `ticket-postgres` container from the notebooks running, stop it first
> (`docker stop ticket-postgres && docker rm ticket-postgres`): same name, same host port 5433.

## Everyday commands

```bash
docker compose up -d --build                      # start in the background (rebuild if code changed)
docker compose ps                                 # status + health of the three services
docker compose logs -f api                        # follow the API logs
docker compose exec api python manage.py seed     # reset tickets to 3 sample tickets (DESTRUCTIVE)
docker compose exec api python demo.py            # scripted chats for alice / bob / carol
docker compose exec api python manage.py reset --users alice bob   # wipe tickets + those users' Mem0 memories
docker compose down                               # stop and remove containers (tickets survive in the volume)
docker compose down -v                            # ...and delete the database volume too
```

Try the API directly:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/tickets
curl -X POST http://localhost:8000/chat -H "Content-Type: application/json" \
     -d "{\"user_id\": \"alice\", \"session_id\": \"test-1\", \"message\": \"Create a high priority ticket to fix the login bug\"}"
```

## What gets traced

One `POST /chat` = one Langfuse **trace** named `handle-chat-turn`:

```
handle-chat-turn   (user_id, session_id, tags, version on every observation below)
 |- retrieve-memories    Mem0 lookup               (retriever)
 |- ticket-agent         LangGraph agent
 |   |- ChatOpenAI       LLM calls, with model + token usage
 |   '- tool calls       create_ticket, update_ticket_status, web_search ...
 '- save-memories        Mem0 write
```

| Langfuse page | What to look at                                                                             |
| ------------- | ------------------------------------------------------------------------------------------- |
| Tracing       | each turn's tree, latency, cost; filter by environment, tag `api`, score `turn_outcome` |
| Sessions      | one row per `session_id` = a whole conversation as one thread                             |
| Users         | one row per `user_id`: turns, cost, last seen                                             |

Scores on every trace: `turn_outcome` (`success` / `error`) and `tool_calls_count`. A failed turn is marked `ERROR`.
Emails and API keys in inputs/outputs are redacted before leaving the process (`ticket_agent/observability.py`).

## Configuration (`.env`)

| Variable                                         | Purpose                                                                                           |
| ------------------------------------------------ | ------------------------------------------------------------------------------------------------- |
| `OPENAI_API_KEY`, `MEM0_API_KEY`             | required                                                                                          |
| `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` | required (Langfuse project settings -> API keys)                                                  |
| `LANGFUSE_BASE_URL`                            | default EU cloud; `https://us.cloud.langfuse.com` for US, or your self-hosted URL               |
| `LANGFUSE_ENVIRONMENT`                         | default `development`; keeps test traces apart from production ones                             |
| `MODEL_NAME`, `APP_VERSION`                  | model (default `gpt-5-nano`) and the `release` label shown in Langfuse                        |
| `DATABASE_URL`                                 | only used when running **outside** Docker; Compose overrides it with the in-network address |

## Running without Docker for the app (optional)

```bash
docker compose up -d postgres
pip install -r requirements.txt && pip install -r ui/requirements.txt
uvicorn api.main:app --reload            # one worker only
API_URL=http://localhost:8000 streamlit run ui/app.py
```

## Project layout

```
ticket_agent/            the agent package (no web code in here)
  config.py              .env + settings
  observability.py       Langfuse client, masking, trace_turn()
  db.py                  Postgres connection, schema, helpers
  memory.py              Mem0 helpers (@observe)
  agent.py               system prompt, build_agent(), run_agent()
  chat.py                ChatSession: one conversation = one session_id
  tools/                 5 ticket tools (Postgres) + web_search
api/main.py              FastAPI: /chat /tickets /memories/{user_id} /health
ui/                      Streamlit app + its own Dockerfile and requirements
Dockerfile               the API image
docker-compose.yml       postgres + api + ui
manage.py, demo.py       housekeeping and scripted demo
```

## Troubleshooting

| Symptom                               | Likely cause                                                                            |
| ------------------------------------- | --------------------------------------------------------------------------------------- |
| `port is already allocated` on 5433 | old `ticket-postgres` container still running (see Quick start)                       |
| `api` stays `unhealthy`           | `docker compose logs api`: usually a missing key in `.env` or a Langfuse auth error |
| UI shows "Cannot load tickets"        | API not healthy yet, or `API_URL` wrong (must be `http://api:8000` inside Compose)  |
| Traces missing in Langfuse            | wrong `LANGFUSE_BASE_URL` region, or keys from a different project                    |
| Edited code but nothing changed       | rebuild: `docker compose up -d --build`                                               |

## Known limitations (by design, for now)

- Conversation history lives in the API process's memory (single worker). Restarting the API clears it;
  tickets (Postgres) and long-term memories (Mem0) survive.
- Tickets are shared by all users; only Mem0 memories are per user.
- No authentication: anyone who can reach port 8000 can send any `user_id`. Local use only.
- Dev-only database credentials are hard-coded in `docker-compose.yml`.
