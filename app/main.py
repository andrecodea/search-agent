import logging
import os
import time
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import RedirectResponse, Response

from app.agent import NewsAgentProtocol, NewspaperAgent
from app.logging_config import configure_logging
from app.schemas import NewsRequest, NewsResponse
from app.settings import Settings, get_settings

load_dotenv()  # Sets LANGSMITH_* and all .env vars in os.environ before LangChain imports run.
configure_logging(os.getenv("LOG_LEVEL", "INFO"))

logger = logging.getLogger(__name__)

HISTORY_DIR = Path(__file__).parent.parent / "history"

app = FastAPI(
    title="AlphaCorp AI Newspaper Delivery Agent",
    version="0.1.0",
    description="Summarises important news from the last 2 days using LangChain, OpenRouter, and Tavily.",
)


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    """Redirect browsers to the Swagger UI."""
    return RedirectResponse(url="/docs")


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    """Return an empty response to suppress browser 404 noise."""
    return Response(status_code=204)


@lru_cache
def build_news_agent() -> NewspaperAgent:
    """Create and cache a NewspaperAgent. Settings are resolved internally via get_settings()."""
    return NewspaperAgent(get_settings())


def get_news_agent() -> NewsAgentProtocol:
    """FastAPI dependency that resolves the cached news agent."""
    return build_news_agent()


def save_to_history(
    response: NewsResponse,
    category: str | None,
    topic: str | None = None,
    history_dir: Path = HISTORY_DIR,
) -> None:
    """Persist a news response as a dated markdown file in the history directory."""
    history_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC)
    label = category or "general"
    filename = f"{now.strftime('%Y-%m-%d_%H-%M-%S')}_{label}.md"
    sources_md = "\n".join(f"- {src}" for src in response.sources)
    topic_line = f"topic: {topic}\n" if topic else ""
    content = (
        f"---\n"
        f"timestamp: {now.isoformat()}\n"
        f"category: {label}\n"
        f"{topic_line}"
        f"---\n\n"
        f"## Summary\n\n{response.summary}\n\n"
        f"## Sources\n\n{sources_md}\n"
    )
    (history_dir / filename).write_text(content, encoding="utf-8")
    logger.info("History entry saved: %s", filename)


@app.post("/news", response_model=NewsResponse)
async def get_news(
    request: NewsRequest,
    agent: NewsAgentProtocol = Depends(get_news_agent),
) -> NewsResponse:
    """Trigger the newspaper agent and return a news summary with sources."""
    category = request.category.value if request.category else None
    topic = request.topic or None
    logger.info("Request received — category: %s  topic: %s", category or "general", topic or "—")

    start_time = time.perf_counter()
    try:
        response = await agent.get_news(category, topic, request.utc_offset_minutes)
    except Exception as exc:
        elapsed = time.perf_counter() - start_time
        logger.exception(
            "Agent failed — category: %s  topic: %s  latency: %.2fs",
            category or "general", topic or "—", elapsed,
        )
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    elapsed = time.perf_counter() - start_time

    logger.info("Request completed — category: %s  topic: %s  latency: %.2fs", category or "general", topic or "—", elapsed)
    save_to_history(response, category, topic)

    return response
