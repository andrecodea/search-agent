# AlphaCorp AI Newspaper Delivery Agent

FastAPI service backed by a LangChain agent that searches for the latest news from the last 2 days, synthesises a plain English summary, and returns up to 5 HTTPS sources. Includes a Streamlit frontend with a news query page and a browsable history viewer.

---

## Architecture

```
POST /news
    │
    ├─ FastAPI validates NewsRequest (Pydantic v2)
    │
    └─ NewspaperAgent.get_news()
         │
         ├─ _compute_date_range(utc_offset_minutes)
         │     Converts UTC now → user's local date to compute
         │     exact 2-day window (start_date / end_date).
         │
         ├─ _build_agent(start_date, end_date)
         │     primary  = create_agent(gemma-4-31b-it, TavilySearch, response_format=NewsResponse)
         │     fallback = create_agent(gemma-4-31b-it:free, ...)
         │     return primary.with_fallbacks([fallback])
         │
         └─ agent.ainvoke(user_message)
               LLM runs 2-3 Tavily queries → discards old results
               → structured output parsed directly as NewsResponse
```

**Key design decisions — full rationale in [`docs/DESIGN.md`](docs/DESIGN.md):**

| Decision | Approach |
|---|---|
| LLM gateway | OpenRouter (OpenAI-compatible). Swap models via `.env`, no code changes. |
| Structured output | `response_format=NewsResponse` — LLM returns a Pydantic model directly, no parsing. |
| Fault tolerance | LangChain Fallback Chain: primary → free-tier fallback, automatic. |
| Date range | Computed from client's UTC offset per request — no timezone drift. |
| DI & testability | `NewsAgentProtocol` (duck typing) + FastAPI `Depends` + `FakeNewsAgent` in tests. |
| Config | `pydantic-settings` reads `.env` once via `@lru_cache`. |
| History | Flat `.md` files with YAML frontmatter — no database dependency. |
| Prompt | External `prompts/system.md` with TOON structure, loaded once at startup. |
| Tracing | LangSmith via env vars — zero code changes to toggle. |

---

## Setup

```bash
cp .env.example .env
# Fill in TAVILY_API_KEY and OPENROUTER_API_KEY

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

| Field | Type | Required | Description |
|---|---|---|---|
| `topic` | string | No | Free-text search topic |
| `category` | string | No | `tech`, `economics`, `politics` |
| `utc_offset_minutes` | int | No | Client UTC offset (auto-sent by frontend) |

Absent `category` and `topic` → general top news.

```json
{
  "summary": "Plain English summary...",
  "sources": ["https://example.com/article"]
}
```

**Example request:**

```bash
curl -X POST http://127.0.0.1:8000/news \
  -H "Content-Type: application/json" \
  -d '{"category": "tech"}'
```

```bash
# With a free-text topic
curl -X POST http://127.0.0.1:8000/news \
  -H "Content-Type: application/json" \
  -d '{"topic": "artificial intelligence", "category": "tech"}'
```

```bash
# General top news (no fields required)
curl -X POST http://127.0.0.1:8000/news \
  -H "Content-Type: application/json" \
  -d '{}'
```

Swagger docs: `http://127.0.0.1:8000/docs`

## Test

```bash
uv run pytest -q
```

## LangSmith

Set `LANGSMITH_TRACING=true` and fill in `LANGSMITH_API_KEY` and `LANGSMITH_PROJECT` in `.env`.

## Environment Variables

See `.env.example` for the full list.
