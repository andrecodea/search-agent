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

**Reason:** Uses LangChain's built-in fault-tolerance mechanism. Both agents are built with the same Tavily tools and system prompt. If the primary model fails (rate limit, timeout, error), the fallback activates automatically. Both models share the same `OPENROUTER_API_KEY`.

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

**Decision:** Store the agent system prompt in `prompts/system.md`, read once at `NewspaperAgent.__init__` and cached on `self._system_prompt`.

**Reason:** Separates prompt engineering from application code. Prompt iteration requires no Python edits. Reading at startup (not per request) eliminates unnecessary disk I/O and surfaces missing-file errors early.

---

## ADR-008 — LLMs Cached; Agent Graph Rebuilt Per Request

**Decision:** Build `primary_llm` and `fallback_llm` in `__init__` (cached via `lru_cache` on `build_news_agent`). Reconstruct Tavily tools and agent graph in `_build_agent()` per request.

**Reason:** LLM client construction is expensive. Tool construction is cheap. This split ensures the LLM is initialised once while `start_date`/`end_date` are always fresh.

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
