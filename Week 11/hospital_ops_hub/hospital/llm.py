"""Shared ChatOpenAI client."""
import os
from functools import lru_cache

from langchain_openai import ChatOpenAI

from .config import MODEL_NAME


def llm_available():
    return bool(os.getenv("OPENAI_API_KEY"))


@lru_cache(maxsize=1)
def get_llm():
    return ChatOpenAI(model=MODEL_NAME, temperature=0, timeout=60, max_retries=2)
