# Newspaper Agent — Full Feature Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the AlphaCorp AI Newspaper Delivery AI Agent with Fallback Chain, external system prompt, structured logging, LangSmith observability, history persistence, and a multi-page Streamlit frontend.

**Architecture:** Async FastAPI backend with a LangChain `create_agent` + Tavily pipeline; primary/fallback LLM chain via OpenRouter; system prompt in `prompts/system.md`; each successful response persisted as a markdown file in `history/`; multi-page Streamlit frontend with news query, and a paginated card-grid history viewer.

**Tech Stack:** FastAPI, pydantic-settings, LangChain, langchain-openai, langchain-tavily, python-dotenv, Streamlit, httpx, pytest, pytest-anyio

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Modify | `app/settings.py` | Add fallback model, max_tokens, log_level, LangSmith fields |
| Modify | `app/schemas.py` | Add docstrings |
| Create | `app/logging_config.py` | `configure_logging(level)` — root logger setup |
| Create | `prompts/system.md` | Agent system prompt (no Python string literals) |
| Modify | `app/agent.py` | `_build_llm`, `_load_system_prompt`, Fallback Chain |
| Modify | `app/main.py` | `load_dotenv`, logging startup, `save_to_history`, request logging |
| Modify | `tests/test_api.py` | Patch `save_to_history` + search routing tests per category |
| Create | `tests/test_settings.py` | Test new Settings field defaults |
| Create | `tests/test_logging_config.py` | Test `configure_logging` level |
| Create | `tests/test_main.py` | Test `save_to_history` file output |
| Modify | `pyproject.toml` | Add `frontend` dependency group |
| Modify | `.env.example` | Add all new env vars |
| Create | `frontend/app.py` | `st.set_page_config` + `st.navigation` |
| Create | `frontend/pages/home.py` | Landing page |
| Create | `frontend/pages/news.py` | Category selector + agent call + results display |
| Create | `frontend/pages/history.py` | Card grid, pagination, full-entry viewer |
| Modify | `docs/DESIGN.md` | Full ADR rewrite reflecting all decisions |
| Modify | `README.md` | Concise English rewrite |

---

## Task 1: Extend Settings (Configuration Object)

**Files:**
- Modify: `app/settings.py`
- Create: `tests/test_settings.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_settings.py`:

```python
from app.settings import Settings


def test_fallback_model_default() -> None:
    assert Settings.model_fields["openrouter_fallback_model"].default == "google/gemma-4-31b-it:free"


def test_max_tokens_default() -> None:
    assert Settings.model_fields["max_tokens"].default == 4096


def test_log_level_default() -> None:
    assert Settings.model_fields["log_level"].default == "INFO"


def test_langsmith_tracing_default() -> None:
    assert Settings.model_fields["langsmith_tracing"].default == "false"


def test_langsmith_endpoint_default() -> None:
    assert Settings.model_fields["langsmith_endpoint"].default == "https://api.smith.langchain.com"
```

- [ ] **Step 2: Run to verify they fail**

```
uv run pytest tests/test_settings.py -v
```

Expected: all 5 fail with `KeyError` or `AssertionError` (fields don't exist yet).

- [ ] **Step 3: Implement the updated Settings**

Replace the full content of `app/settings.py`:

```python
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration object for all service credentials, model parameters, and runtime settings."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Tavily
    tavily_api_key: str = Field(alias="TAVILY_API_KEY")

    # OpenRouter
    openrouter_api_key: str = Field(alias="OPENROUTER_API_KEY")
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        alias="OPENROUTER_BASE_URL",
    )
    openrouter_model: str = Field(
        default="google/gemma-4-31b-it",
        alias="OPENROUTER_MODEL",
    )
    openrouter_fallback_model: str = Field(
        default="google/gemma-4-31b-it:free",
        alias="OPENROUTER_FALLBACK_MODEL",
    )
    max_tokens: int = Field(default=4096, alias="MAX_TOKENS")

    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # LangSmith
    langsmith_tracing: str = Field(default="false", alias="LANGSMITH_TRACING")
    langsmith_api_key: str = Field(default="", alias="LANGSMITH_API_KEY")
    langsmith_project: str = Field(default="", alias="LANGSMITH_PROJECT")
    langsmith_endpoint: str = Field(
        default="https://api.smith.langchain.com",
        alias="LANGSMITH_ENDPOINT",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()
```

- [ ] **Step 4: Run tests to verify they pass**

```
uv run pytest tests/test_settings.py -v
```

Expected: all 5 pass.

- [ ] **Step 5: Commit**

```
git add app/settings.py tests/test_settings.py
git commit -m "feat: extend Settings with fallback model, max_tokens, log level, and LangSmith fields"
```

---

## Task 2: Add Docstrings to Schemas

**Files:**
- Modify: `app/schemas.py`

- [ ] **Step 1: Replace the full content of `app/schemas.py`**

```python
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Category(StrEnum):
    """Supported news categories, aligned with Tavily Search topic values."""

    tech = "tech"
    economics = "economics"
    politics = "politics"


class NewsRequest(BaseModel):
    """Request body for the POST /news endpoint."""

    category: Category | None = None


class NewsResponse(BaseModel):
    """Structured response returned by the newspaper agent."""

    model_config = ConfigDict(str_strip_whitespace=True)

    summary: Annotated[str, Field(min_length=1)]
    sources: Annotated[list[str], Field(max_length=5)]

    @field_validator("sources")
    @classmethod
    def sources_must_be_https(cls, sources: list[str]) -> list[str]:
        """Reject any source that does not use an HTTPS URL."""
        for source in sources:
            if not source.startswith("https://"):
                raise ValueError("All sources must be https links.")
        return sources
```

- [ ] **Step 2: Run existing tests to verify no regression**

```
uv run pytest tests/test_schemas.py -v
```

Expected: all pass.

- [ ] **Step 3: Commit**

```
git add app/schemas.py
git commit -m "docs: add docstrings to Pydantic schemas"
```

---

## Task 3: Create Centralised Logging Config

**Files:**
- Create: `app/logging_config.py`
- Create: `tests/test_logging_config.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_logging_config.py`:

```python
import logging

from app.logging_config import configure_logging


def test_configure_logging_sets_debug_level() -> None:
    configure_logging("DEBUG")
    assert logging.getLogger().level == logging.DEBUG


def test_configure_logging_sets_warning_level() -> None:
    configure_logging("WARNING")
    assert logging.getLogger().level == logging.WARNING


def test_configure_logging_defaults_to_info() -> None:
    configure_logging()
    assert logging.getLogger().level == logging.INFO
```

- [ ] **Step 2: Run to verify they fail**

```
uv run pytest tests/test_logging_config.py -v
```

Expected: fail with `ImportError` (`configure_logging` not found).

- [ ] **Step 3: Create `app/logging_config.py`**

```python
import logging
import sys


def configure_logging(level: str = "INFO") -> None:
    """Configure the root logger with a standard format and a stdout handler.

    Uses `force=True` to replace any handlers already registered by earlier
    calls or third-party libraries (e.g. uvicorn).
    """
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```
uv run pytest tests/test_logging_config.py -v
```

Expected: all 3 pass.

- [ ] **Step 5: Commit**

```
git add app/logging_config.py tests/test_logging_config.py
git commit -m "feat: add centralised logging configuration"
```

---

## Task 4: Create System Prompt File

**Files:**
- Create: `prompts/system.md`

- [ ] **Step 1: Create the `prompts/` directory and `system.md`**

Create `prompts/system.md`:

```markdown
You are a newspaper delivery AI agent. Use the Tavily search tool to find current news before answering. Focus only on stories published within the last 2 days. If the user specifies a category, search within that category only. Write the summary in plain, simple English with no jargon — mention the most important developments, not every search result. Return at most 5 source links, all using https URLs taken directly from the original articles you used. Do not invent sources, fabricate URLs, or include non-news pages.
```

- [ ] **Step 2: Verify the file is readable from the project root**

```
uv run python -c "from pathlib import Path; print(Path('prompts/system.md').read_text())"
```

Expected: prints the prompt text.

- [ ] **Step 3: Commit**

```
git add prompts/system.md
git commit -m "feat: add external system prompt for the newspaper agent"
```

---

## Task 5: Refactor Agent (Fallback Chain + External Prompt)

**Files:**
- Modify: `app/agent.py`

- [ ] **Step 1: Run the existing API tests to establish a baseline**

```
uv run pytest tests/test_api.py -v
```

Expected: all pass (baseline before refactor).

- [ ] **Step 2: Replace the full content of `app/agent.py`**

```python
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol

from langchain.agents import create_agent
from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI
from langchain_tavily import TavilySearch

from app.schemas import NewsResponse
from app.settings import Settings

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


class NewsAgentProtocol(Protocol):
    """Interface for the newspaper agent, enabling dependency injection in tests."""

    async def get_news(self, category: str | None) -> NewsResponse:
        """Fetch and summarise the latest news for the given category."""
        ...


class NewspaperAgent:
    """LangChain agent that searches for recent news via Tavily and returns a structured summary."""

    def __init__(self, settings: Settings) -> None:
        """Build and cache the primary and fallback LLMs from settings."""
        self._settings = settings
        self._primary_llm = self._build_llm(settings.openrouter_model)
        self._fallback_llm = self._build_llm(settings.openrouter_fallback_model)

    async def get_news(self, category: str | None) -> NewsResponse:
        """Run the agent for the given category and return a structured news response."""
        started_at = datetime.now(UTC)
        earliest_date = started_at - timedelta(days=2)
        topic = category or "general top news"

        agent = self._build_agent(
            start_date=earliest_date.date().isoformat(),
            end_date=started_at.date().isoformat(),
        )

        result = await agent.ainvoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            f"Find the latest and most important {topic} from the last "
                            f"2 days only. The current UTC date and time is "
                            f"{started_at.isoformat()}. Do not use stories published "
                            f"before {earliest_date.date().isoformat()}."
                        ),
                    }
                ]
            }
        )

        structured_response = result.get("structured_response")
        if isinstance(structured_response, NewsResponse):
            return structured_response
        return NewsResponse.model_validate(structured_response)

    def _build_llm(self, model: str) -> ChatOpenAI:
        """Instantiate a ChatOpenAI client pointed at OpenRouter for the given model."""
        return ChatOpenAI(
            model=model,
            api_key=self._settings.openrouter_api_key,
            base_url=self._settings.openrouter_base_url,
            temperature=0.2,
            max_tokens=self._settings.max_tokens,
            max_retries=2,
            default_headers={
                "HTTP-Referer": "https://alphacorp.ai",
                "X-Title": "AlphaCorp AI Newspaper Delivery Agent",
            },
        )

    def _build_agent(self, start_date: str, end_date: str) -> Runnable:
        """Build the agent graph with a date-bounded Tavily tool and a primary/fallback chain."""
        tools = [
            TavilySearch(
                api_key=self._settings.tavily_api_key,
                topic="news",
                start_date=start_date,
                end_date=end_date,
                search_depth="advanced",
                max_results=5,
            )
        ]
        system_prompt = _load_system_prompt()

        primary = create_agent(
            model=self._primary_llm,
            tools=tools,
            response_format=NewsResponse,
            system_prompt=system_prompt,
        )
        fallback = create_agent(
            model=self._fallback_llm,
            tools=tools,
            response_format=NewsResponse,
            system_prompt=system_prompt,
        )

        return primary.with_fallbacks([fallback])


def _load_system_prompt() -> str:
    """Read the agent system prompt from prompts/system.md."""
    with open(PROMPTS_DIR / "system.md", encoding="utf-8") as f:
        return f.read()
```

- [ ] **Step 3: Run existing tests to verify no regression**

```
uv run pytest tests/test_api.py tests/test_schemas.py -v
```

Expected: all pass.

- [ ] **Step 4: Commit**

```
git add app/agent.py
git commit -m "feat: refactor agent with Fallback Chain, _build_llm helper, and external system prompt"
```

---

## Task 6: Update main.py (Logging, LangSmith, History)

**Files:**
- Modify: `app/main.py`
- Create: `tests/test_main.py`

- [ ] **Step 1: Write the failing tests for `save_to_history`**

Create `tests/test_main.py`:

```python
from pathlib import Path

import pytest

from app.main import save_to_history
from app.schemas import NewsResponse


def test_save_to_history_creates_markdown_file(tmp_path: Path) -> None:
    response = NewsResponse(
        summary="Tech news summary.",
        sources=["https://example.com/article"],
    )

    save_to_history(response, "tech", history_dir=tmp_path)

    files = list(tmp_path.glob("*.md"))
    assert len(files) == 1


def test_save_to_history_file_contains_frontmatter(tmp_path: Path) -> None:
    response = NewsResponse(
        summary="Tech news summary.",
        sources=["https://example.com/article"],
    )

    save_to_history(response, "tech", history_dir=tmp_path)

    content = next(tmp_path.glob("*.md")).read_text()
    assert "category: tech" in content
    assert "timestamp:" in content


def test_save_to_history_file_contains_summary_and_sources(tmp_path: Path) -> None:
    response = NewsResponse(
        summary="Tech news summary.",
        sources=["https://example.com/article"],
    )

    save_to_history(response, "tech", history_dir=tmp_path)

    content = next(tmp_path.glob("*.md")).read_text()
    assert "Tech news summary." in content
    assert "https://example.com/article" in content


def test_save_to_history_uses_general_for_none_category(tmp_path: Path) -> None:
    response = NewsResponse(
        summary="General news.",
        sources=["https://example.com"],
    )

    save_to_history(response, None, history_dir=tmp_path)

    files = list(tmp_path.glob("*.md"))
    assert "general" in files[0].name


def test_save_to_history_creates_directory_if_missing(tmp_path: Path) -> None:
    history_dir = tmp_path / "nested" / "history"
    response = NewsResponse(
        summary="News.",
        sources=["https://example.com"],
    )

    save_to_history(response, "tech", history_dir=history_dir)

    assert history_dir.exists()
    assert len(list(history_dir.glob("*.md"))) == 1
```

- [ ] **Step 2: Run to verify they fail**

```
uv run pytest tests/test_main.py -v
```

Expected: fail with `ImportError` (`save_to_history` not found in `app.main`).

- [ ] **Step 3: Replace the full content of `app/main.py`**

```python
import logging
import os
import time
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI

from app.agent import NewsAgentProtocol, NewspaperAgent
from app.logging_config import configure_logging
from app.schemas import NewsRequest, NewsResponse
from app.settings import Settings, get_settings

load_dotenv()  # Sets LANGSMITH_* and all .env vars in os.environ before LangChain imports run.
configure_logging(os.getenv("LOG_LEVEL", "INFO"))

logger = logging.getLogger(__name__)

HISTORY_DIR = Path(__file__).parent.parent / "history"

app = FastAPI(
    title="AlphaCorp AI Newspaper Delivery AI Agent",
    version="0.1.0",
    description="Summarises important news from the last 2 days using LangChain, OpenRouter, and Tavily.",
)


@lru_cache
def build_news_agent(settings: Settings) -> NewspaperAgent:
    """Create and cache a NewspaperAgent for the given settings."""
    return NewspaperAgent(settings)


def get_news_agent(settings: Settings = Depends(get_settings)) -> NewsAgentProtocol:
    """FastAPI dependency that resolves the cached news agent."""
    return build_news_agent(settings)


def save_to_history(
    response: NewsResponse,
    category: str | None,
    history_dir: Path = HISTORY_DIR,
) -> None:
    """Persist a news response as a dated markdown file in the history directory."""
    history_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC)
    label = category or "general"
    filename = f"{now.strftime('%Y-%m-%d_%H-%M-%S')}_{label}.md"
    sources_md = "\n".join(f"- {src}" for src in response.sources)
    content = (
        f"---\n"
        f"timestamp: {now.isoformat()}\n"
        f"category: {label}\n"
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
    logger.info("Request received — category: %s", category or "general")

    start_time = time.perf_counter()
    response = await agent.get_news(category)
    elapsed = time.perf_counter() - start_time

    logger.info("Request completed — category: %s  latency: %.2fs", category or "general", elapsed)
    save_to_history(response, category)

    return response
```

- [ ] **Step 4: Run the new tests**

```
uv run pytest tests/test_main.py -v
```

Expected: all 5 pass.

- [ ] **Step 5: Commit**

```
git add app/main.py tests/test_main.py
git commit -m "feat: add logging startup, LangSmith env loading, and save_to_history"
```

---

## Task 7: Patch `save_to_history` and Add Search Routing Tests

**Files:**
- Modify: `tests/test_api.py`

After Task 6, the `get_news` endpoint calls `save_to_history`, which writes real files during tests. Patch it in the fixture. Also add per-category routing tests that verify the correct topic is forwarded to the agent.

- [ ] **Step 1: Update `tests/test_api.py`**

```python
from collections.abc import AsyncIterator
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app, get_news_agent
from app.schemas import NewsResponse


class FakeNewsAgent:
    """Test double for NewspaperAgent — returns a deterministic response without API calls."""

    def __init__(self) -> None:
        self.seen_category: str | None = None

    async def get_news(self, category: str | None) -> NewsResponse:
        """Return a hardcoded response and record the category received."""
        self.seen_category = category
        return NewsResponse(
            summary="Important technology news in simple English.",
            sources=["https://example.com/article"],
        )


@pytest.fixture
async def fake_agent() -> FakeNewsAgent:
    """Reusable FakeNewsAgent instance with save_to_history patched."""
    return FakeNewsAgent()


@pytest.fixture
async def client(fake_agent: FakeNewsAgent) -> AsyncIterator[AsyncClient]:
    """Async test client with FakeNewsAgent injected and save_to_history patched."""
    app.dependency_overrides[get_news_agent] = lambda: fake_agent
    transport = ASGITransport(app=app)

    with patch("app.main.save_to_history"):
        async with AsyncClient(transport=transport, base_url="http://test") as test_client:
            yield test_client

    app.dependency_overrides.clear()


# ── Response shape ────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_post_news_returns_summary_and_sources(client: AsyncClient) -> None:
    response = await client.post("/news", json={"category": "tech"})

    assert response.status_code == 200
    body = response.json()
    assert body["summary"] == "Important technology news in simple English."
    assert body["sources"] == ["https://example.com/article"]


@pytest.mark.anyio
async def test_post_news_accepts_empty_body_for_general_news(client: AsyncClient) -> None:
    response = await client.post("/news", json={})

    assert response.status_code == 200
    assert "summary" in response.json()
    assert "sources" in response.json()


@pytest.mark.anyio
async def test_post_news_rejects_unknown_category(client: AsyncClient) -> None:
    response = await client.post("/news", json={"category": "sports"})

    assert response.status_code == 422


# ── Search routing — correct topic forwarded to agent ────────────────────────

@pytest.mark.anyio
async def test_tech_category_forwards_tech_to_agent(
    client: AsyncClient, fake_agent: FakeNewsAgent
) -> None:
    await client.post("/news", json={"category": "tech"})

    assert fake_agent.seen_category == "tech"


@pytest.mark.anyio
async def test_economics_category_forwards_economics_to_agent(
    client: AsyncClient, fake_agent: FakeNewsAgent
) -> None:
    await client.post("/news", json={"category": "economics"})

    assert fake_agent.seen_category == "economics"


@pytest.mark.anyio
async def test_politics_category_forwards_politics_to_agent(
    client: AsyncClient, fake_agent: FakeNewsAgent
) -> None:
    await client.post("/news", json={"category": "politics"})

    assert fake_agent.seen_category == "politics"


@pytest.mark.anyio
async def test_no_category_forwards_none_to_agent(
    client: AsyncClient, fake_agent: FakeNewsAgent
) -> None:
    await client.post("/news", json={})

    assert fake_agent.seen_category is None


@pytest.mark.anyio
async def test_dummy_query_returns_valid_response_shape(client: AsyncClient) -> None:
    """Smoke test: any valid request produces the expected JSON keys."""
    response = await client.post("/news", json={"category": "tech"})

    body = response.json()
    assert set(body.keys()) == {"summary", "sources"}
    assert isinstance(body["summary"], str)
    assert isinstance(body["sources"], list)


@pytest.mark.anyio
async def test_general_news_query_returns_valid_response_shape(client: AsyncClient) -> None:
    """Smoke test: a request with no topic produces the expected JSON keys."""
    response = await client.post("/news", json={})

    body = response.json()
    assert set(body.keys()) == {"summary", "sources"}
    assert isinstance(body["summary"], str)
    assert isinstance(body["sources"], list)
```

- [ ] **Step 2: Run the full test suite**

```
uv run pytest -v
```

Expected: all tests pass, no files written to `history/` during the run.

- [ ] **Step 3: Commit**

```
git add tests/test_api.py
git commit -m "test: add per-category search routing tests and patch save_to_history"
```

---

## Task 8: Update `pyproject.toml` and `.env.example`

**Files:**
- Modify: `pyproject.toml`
- Modify: `.env.example`

- [ ] **Step 1: Add the `frontend` dependency group to `pyproject.toml`**

Open `pyproject.toml` and update the `[dependency-groups]` section:

```toml
[dependency-groups]
dev = [
    "httpx>=0.28.0",
    "pytest>=8.3.0",
    "pytest-anyio>=0.0.0",
]
frontend = [
    "streamlit>=1.40.0",
]
```

- [ ] **Step 2: Replace `.env.example` with the full list of variables**

```
# Tavily
TAVILY_API_KEY=your-tavily-api-key

# OpenRouter
OPENROUTER_API_KEY=your-openrouter-api-key
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=google/gemma-4-31b-it
OPENROUTER_FALLBACK_MODEL=google/gemma-4-31b-it:free
MAX_TOKENS=4096

# Logging
LOG_LEVEL=INFO

# LangSmith (set LANGSMITH_TRACING=true to enable)
LANGSMITH_TRACING=false
LANGSMITH_API_KEY=your-langsmith-api-key
LANGSMITH_PROJECT=newspaper-agent
LANGSMITH_ENDPOINT=https://api.smith.langchain.com

# Frontend
API_URL=http://localhost:8000/news
```

- [ ] **Step 3: Install the frontend group and verify**

```
uv sync --group frontend
uv run python -c "import streamlit; print(streamlit.__version__)"
```

Expected: prints a version string (e.g. `1.44.0`).

- [ ] **Step 4: Commit**

```
git add pyproject.toml .env.example uv.lock
git commit -m "chore: add frontend dependency group and update .env.example"
```

---

## Task 9: Create Frontend Entry Point and Home Page

**Files:**
- Create: `frontend/app.py`
- Create: `frontend/pages/home.py`

- [ ] **Step 1: Create `frontend/pages/` directory and `frontend/app.py`**

```python
"""
AlphaCorp AI Newspaper Delivery Agent — Streamlit frontend.

Pages:
  - Home:    product overview and quick-start link
  - News:    query the agent by category
  - History: paginated card grid of past summaries
"""

import streamlit as st
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())


def main() -> None:
    """Configure the page and register the navigation structure."""
    st.set_page_config(
        page_title="AlphaCorp AI Newspaper Agent",
        page_icon=":material/newspaper:",
        layout="wide",
    )

    pages = [
        st.Page("pages/home.py", title="Home", icon=":material/home:"),
        st.Page("pages/news.py", title="News", icon=":material/newspaper:"),
        st.Page("pages/history.py", title="History", icon=":material/history:"),
    ]

    page = st.navigation(pages)
    page.run()

    st.sidebar.caption(
        "Built with [LangChain](https://langchain.com) + [Tavily](https://tavily.com). "
        "Powered by [OpenRouter](https://openrouter.ai)."
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Create `frontend/pages/home.py`**

```python
import streamlit as st

st.title("AlphaCorp AI Newspaper Delivery Agent")
st.caption(
    "Stay informed — get a plain English summary of the most important "
    "news from the last 2 days."
)

st.divider()

col_topic, col_search, col_sources = st.columns(3)

with col_topic:
    st.markdown("#### Pick a Topic")
    st.markdown(
        "Select **Tech**, **Economics**, or **Politics**, "
        "or leave it blank for a general news digest."
    )

with col_search:
    st.markdown("#### AI-Powered Search")
    st.markdown(
        "The agent uses Tavily to search the web for the latest stories "
        "and synthesises a concise summary in plain English."
    )

with col_sources:
    st.markdown("#### Cited Sources")
    st.markdown(
        "Every summary comes with up to 5 HTTPS source links "
        "so you can read the full stories."
    )

st.divider()
st.page_link("pages/news.py", label="Get today's news", icon=":material/arrow_forward:")
```

- [ ] **Step 3: Verify the app launches without errors**

```
cd frontend && uv run streamlit run app.py --server.headless true &
sleep 3 && curl -s http://localhost:8501/healthz | grep -i ok
```

Expected: response contains `ok` (Streamlit health endpoint). Kill the background process after verification.

- [ ] **Step 4: Commit**

```
git add frontend/app.py frontend/pages/home.py
git commit -m "feat: add Streamlit frontend entry point and home page"
```

---

## Task 10: Create News Page

**Files:**
- Create: `frontend/pages/news.py`

- [ ] **Step 1: Create `frontend/pages/news.py`**

```python
import os

import httpx
import streamlit as st

API_URL: str = os.getenv("API_URL", "http://localhost:8000/news")

st.title("News")
st.caption("Select a category and let the agent find the most important stories from the last 2 days.")

# ----------------------
# |     UTILITIES      |
# ----------------------


def call_api(category: str | None) -> dict:
    """POST to the news endpoint and return the parsed JSON response."""
    payload = {"category": category} if category else {}
    response = httpx.post(API_URL, json=payload, timeout=120)
    response.raise_for_status()
    return response.json()


# ----------------------
# |      INPUT         |
# ----------------------

CATEGORY_OPTIONS: list[str] = ["General", "Tech", "Economics", "Politics"]

selected_category: str = st.selectbox("Category", options=CATEGORY_OPTIONS, index=0)
category_value: str | None = None if selected_category == "General" else selected_category.lower()

run_button = st.button("Get News", type="primary", icon=":material/newspaper:")

st.divider()

# ----------------------
# |     SESSION        |
# ----------------------

if "summary" not in st.session_state:
    st.session_state.summary = ""
    st.session_state.sources = []

# ----------------------
# |     RESULTS        |
# ----------------------

if run_button:
    st.session_state.summary = ""
    st.session_state.sources = []
    with st.spinner("Searching for the latest news..."):
        try:
            data = call_api(category_value)
            st.session_state.summary = data.get("summary", "")
            st.session_state.sources = data.get("sources", [])
        except Exception as exc:
            st.error(f"Request failed: {exc}")

if st.session_state.summary:
    st.subheader("Summary")
    st.markdown(st.session_state.summary)

    if st.session_state.sources:
        st.subheader("Sources")
        for source_url in st.session_state.sources:
            st.link_button(source_url, source_url, icon=":material/open_in_new:")
```

- [ ] **Step 2: Run the full test suite (backend) to confirm nothing broke**

```
uv run pytest -v
```

Expected: all pass.

- [ ] **Step 3: Commit**

```
git add frontend/pages/news.py
git commit -m "feat: add Streamlit news query page"
```

---

## Task 11: Create History Page

**Files:**
- Create: `frontend/pages/history.py`

- [ ] **Step 1: Create `frontend/pages/history.py`**

```python
import re
from math import ceil
from pathlib import Path

import streamlit as st

HISTORY_DIR: Path = Path(__file__).parent.parent.parent / "history"
CARDS_PER_PAGE: int = 9

st.title("History")
st.caption("Past news summaries retrieved by the agent.")

# ----------------------
# |     UTILITIES      |
# ----------------------


def parse_history_file(file_path: Path) -> dict:
    """Parse a history markdown file into its frontmatter metadata and body text."""
    content = file_path.read_text(encoding="utf-8")
    parts = content.split("---\n", 2)
    frontmatter: dict[str, str] = {}
    if len(parts) >= 2:
        for line in parts[1].strip().splitlines():
            key, _, value = line.partition(": ")
            frontmatter[key.strip()] = value.strip()
    body = parts[2].strip() if len(parts) > 2 else ""
    return {
        "timestamp": frontmatter.get("timestamp", ""),
        "category": frontmatter.get("category", "general"),
        "body": body,
    }


def extract_summary_preview(body: str, max_chars: int = 120) -> str:
    """Return a short preview of the summary section, truncated to max_chars."""
    match = re.search(r"## Summary\n\n(.*?)(?=\n## |\Z)", body, re.DOTALL)
    if not match:
        return ""
    text = match.group(1).strip()
    return text[:max_chars] + "..." if len(text) > max_chars else text


def extract_sources(body: str) -> list[str]:
    """Return all HTTPS URLs from the sources section of the body."""
    match = re.search(r"## Sources\n\n(.*?)(?=\n## |\Z)", body, re.DOTALL)
    if not match:
        return []
    return re.findall(r"https://\S+", match.group(1))


def format_timestamp(iso_timestamp: str) -> str:
    """Convert an ISO timestamp to a human-readable display string."""
    return iso_timestamp[:19].replace("T", " ") + " UTC"


# ----------------------
# |     SESSION        |
# ----------------------

if "history_page" not in st.session_state:
    st.session_state.history_page = 0
if "selected_history_file" not in st.session_state:
    st.session_state.selected_history_file = None

# ----------------------
# |      GRID          |
# ----------------------

if not HISTORY_DIR.exists() or not list(HISTORY_DIR.glob("*.md")):
    st.info("No history yet. Run a news query on the News page to see results here.")
    st.stop()

history_files: list[Path] = sorted(HISTORY_DIR.glob("*.md"), reverse=True)
total_pages: int = ceil(len(history_files) / CARDS_PER_PAGE)
current_page: int = min(st.session_state.history_page, total_pages - 1)
page_files: list[Path] = history_files[current_page * CARDS_PER_PAGE : (current_page + 1) * CARDS_PER_PAGE]

grid_columns = st.columns(3)
for card_index, file_path in enumerate(page_files):
    entry = parse_history_file(file_path)
    preview = extract_summary_preview(entry["body"])
    timestamp_display = format_timestamp(entry["timestamp"])

    with grid_columns[card_index % 3]:
        with st.container(border=True):
            st.caption(f"📅 {timestamp_display}  🏷 {entry['category'].capitalize()}")
            st.markdown(preview)
            if st.button("View", key=f"view_{file_path.name}"):
                st.session_state.selected_history_file = file_path.name
                st.rerun()

st.divider()

# ----------------------
# |    PAGINATION      |
# ----------------------

col_prev, col_info, col_next = st.columns([1, 2, 1])
with col_prev:
    if st.button("← Prev", disabled=current_page == 0):
        st.session_state.history_page -= 1
        st.rerun()
with col_info:
    st.caption(f"Page {current_page + 1} of {total_pages}")
with col_next:
    if st.button("Next →", disabled=current_page == total_pages - 1):
        st.session_state.history_page += 1
        st.rerun()

# ----------------------
# |    SELECTED        |
# ----------------------

if st.session_state.selected_history_file:
    selected_path = HISTORY_DIR / st.session_state.selected_history_file
    if selected_path.exists():
        entry = parse_history_file(selected_path)
        sources = extract_sources(entry["body"])

        st.divider()
        st.subheader(
            f"{entry['category'].capitalize()} — {format_timestamp(entry['timestamp'])}"
        )

        summary_match = re.search(r"## Summary\n\n(.*?)(?=\n## |\Z)", entry["body"], re.DOTALL)
        if summary_match:
            st.markdown(summary_match.group(1).strip())

        if sources:
            st.subheader("Sources")
            for source_url in sources:
                st.link_button(source_url, source_url, icon=":material/open_in_new:")
```

- [ ] **Step 2: Run the full test suite to confirm no regressions**

```
uv run pytest -v
```

Expected: all pass.

- [ ] **Step 3: Commit**

```
git add frontend/pages/history.py
git commit -m "feat: add Streamlit history page with card grid and pagination"
```

---

## Task 12: Update DESIGN.md and README.md

**Files:**
- Modify: `docs/DESIGN.md`
- Modify: `README.md`

- [ ] **Step 1: Replace `docs/DESIGN.md`**

```markdown
# Design Decisions

## Project Goal

AI agent that fetches the most important news from the last 2 days on a given topic and returns a plain English summary with up to 5 HTTPS sources, via `POST /news` on an async FastAPI service with a Streamlit frontend.

---

## ADR-001 — FastAPI as HTTP Layer

**Decision:** FastAPI with Pydantic v2 for I/O validation.

**Reason:** Auto-generated Swagger docs, declarative validation, and native `async/await` support compatible with the async LangChain agent invocation.

---

## ADR-002 — LangChain `create_agent` as Orchestrator

**Decision:** Use `langchain.agents.create_agent` with `response_format=NewsResponse`.

**Reason:** `response_format` forces the LLM to return structured output directly as a Pydantic model, eliminating manual response parsing. The agent decides autonomously how many times to call Tavily before composing the final answer.

---

## ADR-003 — OpenRouter as LLM Gateway

**Decision:** Use `ChatOpenAI` pointed at `https://openrouter.ai/api/v1` (OpenAI-compatible interface).

**Reason:** OpenRouter unifies access to multiple model providers via a single API. Changing models requires only a `.env` update, no code changes.

- **Primary model:** `google/gemma-4-31b-it`
- **Fallback model:** `google/gemma-4-31b-it:free` (same provider, free tier)

---

## ADR-004 — Fallback Chain

**Decision:** `primary_agent.with_fallbacks([fallback_agent])` — LangChain native fallback.

**Reason:** Uses LangChain's built-in fault-tolerance mechanism. Both agents are built with the same Tavily tools and system prompt. If the primary model fails (rate limit, timeout, error), the fallback activates automatically.

Both models share the same `OPENROUTER_API_KEY`. Cost separation can be achieved with separate OpenRouter accounts if needed.

---

## ADR-005 — Tavily Search as the Only Tool

**Decision:** Register only `TavilySearch` as an agent tool, with `start_date`/`end_date` computed per request.

**Reason:** Tavily specialises in recent news with date filtering. `time_range="day"` was rejected because it only covers 1 day; `start_date = today - 2 days` / `end_date = today` gives the exact 2-day window. These dates are computed fresh on each `get_news()` call — not at agent construction time — to avoid stale values in long-running processes.

---

## ADR-006 — pydantic-settings as Configuration Object

**Decision:** `Settings(BaseSettings)` reads all configuration from `.env` via explicit field aliases. No defaults or constants in Python files.

**Reason:** Single source of truth for all config. `@lru_cache` on `get_settings()` ensures the `.env` file is read once per process lifetime.

---

## ADR-007 — External System Prompt in `prompts/system.md`

**Decision:** Store the agent system prompt in `prompts/system.md`, read via `open()` context manager inside `_build_agent()`.

**Reason:** Separates prompt engineering from application code. Prompt iteration requires no Python edits. The file is read per request, which is negligible I/O for a small text file.

---

## ADR-008 — LLMs Cached; Agent Graph Rebuilt Per Request

**Decision:** Build `primary_llm` and `fallback_llm` in `__init__` (cached via `lru_cache` on `build_news_agent`). Reconstruct Tavily tools and agent graph in `_build_agent()` per request.

**Reason:** LLM client construction is expensive. Tool construction is cheap. This split ensures the LLM is initialised once while dates are always fresh.

---

## ADR-009 — `NewsAgentProtocol` for Testable Dependency Injection

**Decision:** Structural subtype protocol (`typing.Protocol`) with `async def get_news(category) -> NewsResponse`. Injected via FastAPI `Depends`.

**Reason:** Tests replace `NewspaperAgent` with `FakeNewsAgent` via `app.dependency_overrides`, sidestepping all external API calls. No inheritance required — duck typing.

---

## ADR-010 — History Persistence as Flat Markdown Files

**Decision:** One `.md` file per response in `history/`, named `YYYY-MM-DD_HH-MM-SS_<category>.md` with YAML-style frontmatter.

**Reason:** No database dependency, no new packages, human-readable outside the app. Chronological order comes free from filenames. SQLite would be the next step if category filtering or full-text search were needed.

---

## ADR-011 — LangSmith via Environment Variables

**Decision:** `load_dotenv()` at the top of `main.py` sets `LANGSMITH_*` in `os.environ`. LangChain auto-detects and enables tracing.

**Reason:** Zero code changes required to toggle tracing. The application is unaware of LangSmith beyond loading the env file.

---

## Design Patterns Summary

| Pattern | Location | Purpose |
|---|---|---|
| Configuration Object | `app/settings.py` | Single source of truth for all config |
| Fallback Chain | `app/agent.py` | LLM fault tolerance |
| Protocol / Structural Subtyping | `NewsAgentProtocol` | Testable dependency injection |
| Singleton via `lru_cache` | `get_settings`, `build_news_agent` | One instance per process |
| Structured Output | `response_format=NewsResponse` | LLM returns Pydantic model directly |
| Fake Object | `FakeNewsAgent` | Tests without external API calls |
| External Prompt | `prompts/system.md` | Prompt decoupled from Python code |

---

## I/O Contracts

### Request — `POST /news`

```json
{ "category": "tech" }
```

`category` optional. Valid values: `tech`, `economics`, `politics`. Absent → general news search.

### Response

```json
{
  "summary": "Plain English summary...",
  "sources": ["https://..."]
}
```

**Pydantic invariants:**
- `summary`: non-empty string
- `sources`: max 5 items, all prefixed with `https://`
```

- [ ] **Step 2: Replace `README.md`**

```markdown
# AlphaCorp AI Newspaper Delivery AI Agent

FastAPI service that exposes a `POST /news` endpoint backed by a LangChain agent. The agent searches for the latest news from the last 2 days using Tavily, synthesises a plain English summary, and returns up to 5 HTTPS sources. Includes a Streamlit frontend with a news query page and a browsable history viewer.

## Setup

```bash
cp .env.example .env
# Fill in API keys
uv sync                    # backend
uv sync --group frontend   # Streamlit frontend
```

## Run

```bash
# Backend
uv run uvicorn app.main:app --reload

# Frontend (separate terminal, from project root)
cd frontend && uv run streamlit run app.py
```

## API

**`POST /news`**

| Field | Type | Required | Values |
|---|---|---|---|
| `category` | string | No | `tech`, `economics`, `politics` |

Absent `category` → general top news.

Response:
```json
{
  "summary": "Plain English summary...",
  "sources": ["https://example.com/article"]
}
```

Swagger docs: `http://127.0.0.1:8000/docs`

## Test

```bash
uv run pytest -q
uv run pytest tests/test_api.py::test_post_news_returns_agent_response -q
```

## LangSmith

Set `LANGSMITH_TRACING=true` and fill in `LANGSMITH_API_KEY` and `LANGSMITH_PROJECT` in `.env` to enable tracing.

## Environment Variables

See `.env.example` for the full list.
```

- [ ] **Step 3: Run the full test suite one final time**

```
uv run pytest -v
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```
git add docs/DESIGN.md README.md
git commit -m "docs: rewrite DESIGN.md with full ADRs and update README to English"
```

---

## Self-Review Checklist

- [x] **Spec coverage:**
  - Configuration Object → Task 1
  - Fallback Chain (gemma → gemma:free) → Task 5
  - `max_tokens=4096` via env → Task 1 + 5
  - External prompt in `prompts/` → Task 4 + 5
  - Logging → Task 3 + 6
  - LangSmith → Task 6 + 8
  - History (markdown files) → Task 6
  - Frontend: home + news + history pages → Tasks 9–11
  - Card grid + pagination → Task 11
  - Type hints + docstrings → Tasks 2, 3, 5, 6, 9–11
  - Nothing hardcoded → Tasks 1, 8
  - `.env.example` updated → Task 8
  - `DESIGN.md` + `README.md` → Task 12

- [x] **No placeholders** — all steps contain complete code.

- [x] **Type consistency:**
  - `save_to_history(response: NewsResponse, category: str | None, history_dir: Path)` defined in Task 6 and tested in Task 6.
  - `_build_llm(model: str) -> ChatOpenAI` defined in Task 5, called in Task 5.
  - `parse_history_file`, `extract_summary_preview`, `extract_sources`, `format_timestamp` defined and used only within Task 11.
  - `HISTORY_DIR` defined in `app/main.py` (Task 6) and separately in `frontend/pages/history.py` (Task 11) — two independent path computations for two independent modules.
