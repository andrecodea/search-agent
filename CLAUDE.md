# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

FastAPI service that exposes a `POST /news` endpoint backed by a LangChain agent. The agent queries Tavily for recent news (last 2 days) via OpenRouter and returns a structured `NewsResponse` with a plain-English summary and up to 5 HTTPS source links. Includes a Streamlit frontend (Home, News, History pages).

## Commands

```bash
# Install dependencies
uv sync
uv sync --group frontend   # includes streamlit, httpx

# Run dev server
uv run uvicorn app.main:app --reload

# Run frontend (from project root)
cd frontend && uv run streamlit run app.py

# Run all tests
uv run pytest -q

# Run a single test file
uv run pytest tests/test_api.py -q

# Run a single test by name
uv run pytest tests/test_api.py::test_post_news_returns_summary_and_sources -q
```

## Architecture

```
app/
  settings.py       # pydantic-settings; all config via .env, @lru_cache singleton
  schemas.py        # Category (StrEnum), NewsRequest, NewsResponse
  agent.py          # NewspaperAgent, NewsAgentProtocol, _compute_date_range
  logging_config.py # configure_logging() — root logger, stdout, force=True
  main.py           # FastAPI app, DI, save_to_history, POST /news endpoint
prompts/
  system.md         # Agent system prompt (TOON structure), loaded once at startup
frontend/
  app.py            # Streamlit entry point, st.navigation
  pages/
    home.py         # Landing page
    news.py         # Search form, calls POST /news, renders summary + sources
    history.py      # Paginated card grid of history/ files
tests/
  test_api.py          # Async integration tests (FakeNewsAgent + ASGITransport)
  test_schemas.py      # Pure Pydantic unit tests
  test_date_range.py   # _compute_date_range invariants + NewsResponse validators
  test_main.py         # save_to_history unit tests
  test_settings.py     # Settings defaults
  test_logging_config.py
docs/
  DESIGN.md         # ADR-001 to ADR-015, spec compliance section, I/O contracts
  BUGS.md           # BUG-001 to BUG-004 with root causes and fixes
history/            # Runtime output — one .md per request (gitignored)
```

## Key Design Decisions

**Singleton pattern:** `get_settings()` is `@lru_cache`. `build_news_agent()` is also `@lru_cache` — zero-argument, calls `get_settings()` internally. `Settings` is not hashable (Pydantic BaseSettings), so it cannot be passed as an argument to a cached function (BUG-001).

**DI pattern:** `NewsAgentProtocol(Protocol)` — structural duck typing, no inheritance. Tests inject `FakeNewsAgent` via `app.dependency_overrides[get_news_agent]`. `save_to_history` is patched separately with `unittest.mock.patch`.

**Agent internals:** `NewspaperAgent.__init__` builds `primary_llm` and `fallback_llm` once. `_build_agent(start_date, end_date)` is called per request (dates must be fresh). Returns `primary.with_fallbacks([fallback])`. `response_format=NewsResponse` forces structured LLM output parsed directly into Pydantic.

**Timezone-aware dates:** Frontend sends `utc_offset_minutes` (detected via `datetime.now().astimezone().utcoffset()`). `_compute_date_range(utc_offset_minutes, now=None)` is a pure function — accepts optional `now` for deterministic tests (BUG-002).

**Tavily config:** `search_depth="basic"`, `max_results=3`, `topic="news"`, `start_date`/`end_date` per request.

**LLM config:** `model_kwargs={"parallel_tool_calls": True}`, `max_tokens=2048`, `temperature=0.2`.

**Windows:** `asyncio.WindowsSelectorEventLoopPolicy()` set on `sys.platform == "win32"` to suppress `ConnectionResetError` noise (BUG-004).

**load_dotenv() placement:** Called at the top of `main.py` before any LangChain import — LangChain reads `LANGSMITH_TRACING` at import time.

## Spec Compliance

The task spec requires only `category` as optional input field. The project also accepts `topic` (free-text) and `utc_offset_minutes` (timezone fix) — both optional, both backwards-compatible. Documented in `docs/DESIGN.md` under "Spec Compliance & Extensions".

## Async Tests

`pytest-anyio`. All async test functions and async fixtures must be decorated with `@pytest.mark.anyio`. The `client` fixture is async and yields an `AsyncClient` with `ASGITransport`.

## Environment

Copy `.env.example` to `.env` and fill in:

| Variable | Purpose |
|---|---|
| `TAVILY_API_KEY` | Tavily search API |
| `OPENROUTER_API_KEY` | OpenRouter LLM gateway |
| `OPENROUTER_BASE_URL` | Default: `https://openrouter.ai/api/v1` |
| `OPENROUTER_MODEL` | Default: `google/gemma-4-31b-it` |
| `OPENROUTER_FALLBACK_MODEL` | Default: `google/gemma-4-31b-it:free` |
| `MAX_TOKENS` | Default: `2048` |
| `LANGSMITH_TRACING` | `true` to enable LangSmith tracing |
| `LANGSMITH_API_KEY` | LangSmith API key |
| `LANGSMITH_PROJECT` | LangSmith project name |
