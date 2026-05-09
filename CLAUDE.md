# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

FastAPI service that exposes a `POST /news` endpoint backed by a LangChain agent. The agent queries Tavily for recent news (last 2 days) via OpenRouter and returns a structured `NewsResponse` with a plain-English summary and up to 5 HTTPS source links.

## Commands

```bash
# Install dependencies
uv sync

# Run dev server
uv run uvicorn app.main:app --reload

# Run all tests
uv run pytest -q

# Run a single test file
uv run pytest tests/test_api.py -q

# Run a single test by name
uv run pytest tests/test_api.py::test_post_news_returns_agent_response -q
```

## Architecture

```
app/
  settings.py   # pydantic-settings; reads TAVILY_API_KEY / OPENROUTER_* from .env
  schemas.py    # Pydantic models: Category (StrEnum), NewsRequest, NewsResponse
  agent.py      # NewspaperAgent builds a LangChain agent; NewsAgentProtocol for DI
  main.py       # FastAPI app; wires settings → agent via lru_cache + Depends
tests/
  test_schemas.py  # pure unit tests (no HTTP)
  test_api.py      # async integration tests using FakeNewsAgent + httpx ASGITransport
docs/
  DESIGN.md        # architecture decisions and design patterns
```

**Dependency injection pattern:** `get_settings()` is `@lru_cache`-cached. `build_news_agent(settings)` is also `@lru_cache`-cached (one agent per unique `Settings` instance). Tests override `get_news_agent` via `app.dependency_overrides` with a `FakeNewsAgent` — this sidesteps both the LLM and Tavily.

**Agent internals:** `NewspaperAgent._build_agent()` creates a `ChatOpenAI` pointing at OpenRouter, a `TavilySearch` tool (topic=news, time_range=day), and calls `langchain.agents.create_agent` with `response_format=NewsResponse` so the LLM output is parsed directly into the Pydantic schema.

**Async tests:** The test suite uses `pytest-anyio`. Async fixtures and test functions must be decorated with `@pytest.mark.anyio`.

## Documentation

Design decisions and architectural patterns are in `docs/DESIGN.md`.

## Environment

Copy `.env.example` to `.env` and fill in:

| Variable | Purpose |
|---|---|
| `TAVILY_API_KEY` | Tavily search API |
| `OPENROUTER_API_KEY` | OpenRouter LLM gateway |
| `OPENROUTER_BASE_URL` | Default: `https://openrouter.ai/api/v1` |
| `OPENROUTER_MODEL` | Default: `google/gemma-4-31b-it` |
