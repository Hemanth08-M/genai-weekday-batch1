"""Configuration: load .env once, expose typed settings."""
import os
from dataclasses import dataclass

from dotenv import load_dotenv

# Must run BEFORE the Langfuse client is created, so it can see the keys.
load_dotenv()

# Default to the EU cloud; override in .env for US cloud or a self-hosted instance.
os.environ.setdefault("LANGFUSE_BASE_URL", "https://cloud.langfuse.com")

REQUIRED_KEYS = (
    "OPENAI_API_KEY",
    "MEM0_API_KEY",
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
)


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "postgresql://ticket_user:ticket_pass@localhost:5433/tickets")
    model_name: str = os.getenv("MODEL_NAME", "gpt-5-nano")
    app_version: str = os.getenv("APP_VERSION", "ticket-agent-1.0")  # shown as `release` / `version` in Langfuse
    environment: str = os.getenv("LANGFUSE_ENVIRONMENT", "development")
    short_term_turns: int = 4  # how many past turns the agent sees as chat history


settings = Settings()


def check_env() -> None:
    """Fail early with a clear message instead of a stack trace deep inside a library."""
    missing = [k for k in REQUIRED_KEYS if not os.environ.get(k)]
    if missing:
        raise RuntimeError(
            f"Missing environment variables: {', '.join(missing)}. Copy .env.example to .env and fill them in."
        )
