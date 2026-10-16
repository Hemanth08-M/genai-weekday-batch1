"""Web search via the Tavily API (needs TAVILY_API_KEY)."""
import logging
import os

from langchain_core.tools import tool
from tavily import TavilyClient

log = logging.getLogger(__name__)


def _search(query: str, n: int = 4) -> list[dict]:
    try:
        client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
        results = client.search(query, max_results=n)["results"]
        return [{"title": r["title"], "href": r["url"], "body": r["content"]} for r in results]
    except Exception as exc:  # missing key / network / rate-limit: the agent gets "No results." instead of a crash
        log.warning("web_search failed: %s", type(exc).__name__)
        return []


def _format(results: list[dict]) -> str:
    if not results:
        return "No results."
    return "\n\n".join(f"[{i}] {r['title']}\n{r['href']}\n{r['body']}" for i, r in enumerate(results, 1))


@tool
def web_search(query: str) -> str:
    """Search the web and return the top results (title, url, snippet)."""
    return _format(_search(query))
