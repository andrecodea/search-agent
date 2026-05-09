# Spec: AlphaCorp AI Newspaper Delivery AI Agent

**Date:** 2026-05-08
**Status:** Approved

---

## Goal

An AI agent that finds the most important news from the last 2 days on a given topic and returns a plain English summary with up to 5 verified HTTPS sources, exposed via `POST /news` on an async FastAPI service with a Streamlit frontend.

---

## Functional Requirements

- `POST /news` accepts `{"category": "tech"|"economics"|"politics"}` (optional field)
- No `category` → fetch general top news from the last 2 days
- Response: `{"summary": "<text>", "sources": ["https://..."]}`
- `sources` capped at 5 items; all must start with `https://`
- Time window: `start_date = today - 2 days`, `end_date = today` (computed per request)
- Maximum LLM output: 4096 tokens

## Non-Functional Requirements

- Fully async API (FastAPI + `async/await`)
- Nothing hardcoded: all immutable defaults live in `.env`
- Type hints and docstrings on all functions
- Unambiguous variable names
- Clean, idiomatic Python

---

## Architecture

```
app/
  settings.py        # Configuration Object (pydantic-settings)
  schemas.py         # Pydantic I/O: Category, NewsRequest, NewsResponse
  agent.py           # NewspaperAgent + Fallback Chain
  logging_config.py  # Centralised logging setup
  main.py            # FastAPI app, startup hooks, endpoint
prompts/
  system.md          # Agent system prompt (read via context manager)
history/             # Auto-created; one .md file per agent response
frontend/
  app.py             # st.set_page_config + st.navigation
  pages/
    home.py          # Landing page
    news.py          # Main interface: input + results
    history.py       # Card grid with pagination
docs/
  DESIGN.md
  superpowers/specs/
.env.example
README.md
```

---

## Design Patterns

### Configuration Object (`app/settings.py`)

`Settings(BaseSettings)` centralises all configuration. Read from `.env` via explicit aliases. No configuration value lives outside this class.

Fields:

| Field | Env var | Default |
|---|---|---|
| `tavily_api_key` | `TAVILY_API_KEY` | — |
| `openrouter_api_key` | `OPENROUTER_API_KEY` | — |
| `openrouter_base_url` | `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` |
| `openrouter_model` | `OPENROUTER_MODEL` | `google/gemma-4-31b-it` |
| `openrouter_fallback_model` | `OPENROUTER_FALLBACK_MODEL` | `google/gemma-4-31b-it:free` |
| `max_tokens` | `MAX_TOKENS` | `4096` |
| `log_level` | `LOG_LEVEL` | `INFO` |
| `langsmith_tracing` | `LANGSMITH_TRACING` | `false` |
| `langsmith_api_key` | `LANGSMITH_API_KEY` | `""` |
| `langsmith_project` | `LANGSMITH_PROJECT` | `""` |
| `langsmith_endpoint` | `LANGSMITH_ENDPOINT` | `https://api.smith.langchain.com` |
| `api_url` *(frontend only)* | `API_URL` | `http://localhost:8000/news` |

`get_settings()` is `@lru_cache` — one instance per process.

### Fallback Chain (`app/agent.py`)

```
primary_llm  = ChatOpenAI(model=openrouter_model,          api_key=..., max_tokens=4096)
fallback_llm = ChatOpenAI(model=openrouter_fallback_model, api_key=..., max_tokens=4096)

_build_agent(start_date, end_date):
    tools    = [TavilySearch(start_date, end_date, max_results=5)]
    primary  = create_agent(model=primary_llm,  tools, response_format=NewsResponse, system_prompt)
    fallback = create_agent(model=fallback_llm, tools, response_format=NewsResponse, system_prompt)
    return primary.with_fallbacks([fallback])
```

- `primary_llm` and `fallback_llm` built once in `__init__` (cached via `lru_cache` on `build_news_agent`)
- `_build_agent()` called per request → dates always fresh
- Both models share the same `OPENROUTER_API_KEY`

### External Prompt (`prompts/system.md`)

`_load_system_prompt()` reads `prompts/system.md` via `open()` context manager. Called inside `_build_agent()`. No prompt strings in Python code.

### Protocol for Testable DI (`NewsAgentProtocol`)

`NewsAgentProtocol(Protocol)` declares `async def get_news(category) -> NewsResponse`. Injected via `Depends`. Tests replace it with `FakeNewsAgent` via `app.dependency_overrides`.

---

## Request Flow

```
POST /news {"category": "tech"}
  → FastAPI validates NewsRequest (Pydantic)
  → get_news_agent() → build_news_agent(settings) [lru_cache]
  → agent.get_news("tech")
      → datetime.now(UTC) → start_date, end_date
      → _build_agent(start_date, end_date)
          → TavilySearch(start_date, end_date, max_results=5)
          → primary.with_fallbacks([fallback])
      → agent.ainvoke({messages: [...]})
          → Tavily fetches news (last 2 days)
          → LLM synthesises → structured NewsResponse
          → If primary fails → fallback activates automatically
  → NewsResponse {"summary": "...", "sources": [...]}
  → FastAPI serialises → 200 OK
```

---

## Logging & Observability

**`app/logging_config.py`:** `configure_logging(level)` sets up root logger via `basicConfig` (format: `timestamp [LEVEL] module: msg`, handler: stdout).

**`main.py`:** calls `configure_logging()` at startup. Logs the start and end of each request with category and latency.

**LangSmith:** `load_dotenv()` at the top of `main.py` sets `LANGSMITH_*` in `os.environ`. LangChain auto-detects and starts tracing when `LANGSMITH_TRACING=true`.

---

## Frontend (Streamlit)

Replicates the pattern from `corporate-intelliops-system`:

**`frontend/app.py`:**
- `load_dotenv(find_dotenv())`
- `st.set_page_config(layout="wide")`
- `st.navigation([home, news])` + `st.sidebar.caption`

**`frontend/pages/home.py`:** title, agent description, `st.page_link` to the news page.

**`frontend/pages/news.py`** (sections marked with `# ---- | SECTION | ----`):
- `API_URL` from `os.getenv("API_URL")`
- `call_api(category)` — synchronous `httpx.post`, timeout=120
- `selectbox`: General / Tech / Economics / Politics
- "Get News" button (primary, always enabled — `category` is optional)
- `st.session_state`: `{"summary": "", "sources": []}`
- Display: `st.markdown(summary)` + `st.link_button` per source

**`frontend/pages/history.py`** (sections marked with `# ---- | SECTION | ----`):
- Reads all `.md` files from `history/`, sorted newest-first by filename
- Grid: 3 cards per row via `st.columns(3)` + `st.container(border=True)`
- Each card shows: timestamp, category badge, summary preview (~120 chars), "View" button
- Selection stored in `st.session_state["selected_history_file"]`
- Selected card renders full summary + `st.link_button` per source below the grid
- Pagination: 9 cards per page (3×3); prev/next buttons + page counter via `st.session_state["history_page"]`; `st.rerun()` on page change

**History file format** (`history/YYYY-MM-DD_HH-MM-SS_<category>.md`):
```markdown
---
timestamp: 2026-05-08T14:32:10Z
category: tech
---

## Summary

Plain English summary here...

## Sources

- https://example.com/article-1
```
Written by `main.py` after each successful agent response. `history/` directory is auto-created on first write.

---

## I/O Contracts

### Request
```json
{ "category": "tech" }
```
`category` is optional. Values: `tech`, `economics`, `politics`. Absent → general.

### Response
```json
{
  "summary": "Plain English summary...",
  "sources": ["https://example.com/article"]
}
```

**Pydantic invariants:**
- `summary`: `min_length=1`
- `sources`: `max_length=5`, all prefixed with `https://`

---

## Dependencies

### Backend (`pyproject.toml`)
No new dependencies beyond those already declared.

### Frontend (new `frontend` group)
```
streamlit, httpx, python-dotenv
```

---

## Tests

- `tests/test_schemas.py` — pure unit tests (no HTTP)
- `tests/test_api.py` — async integration via `FakeNewsAgent` + `httpx.ASGITransport`
- `pytest-anyio` for async tests; decorate fixtures and test functions with `@pytest.mark.anyio`
