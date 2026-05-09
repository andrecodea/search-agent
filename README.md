# AlphaCorp AI Newspaper Delivery AI Agent

FastAPI service that exposes a `POST /news` endpoint backed by a LangChain agent. The agent searches for the latest news from the last 2 days using Tavily, synthesises a plain English summary, and returns up to 5 HTTPS sources. Includes a Streamlit frontend with a news query page and a browsable history viewer.

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
```

## LangSmith

Set `LANGSMITH_TRACING=true` and fill in `LANGSMITH_API_KEY` and `LANGSMITH_PROJECT` in `.env` to enable tracing.

## Environment Variables

See `.env.example` for the full list.
