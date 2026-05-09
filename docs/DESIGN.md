# Design Decisions

## Project Goal

AI agent that fetches the most important news from the last 2 days on a given topic and returns a plain English summary with up to 5 HTTPS sources, via `POST /news` on an async FastAPI service with a Streamlit frontend.

---

## Spec Compliance & Extensions

The implementation satisfies 100% of the task spec. Two optional fields were added to `NewsRequest` beyond the original requirement. Both are backwards-compatible — a request with only `{"category": "tech"}` behaves exactly as specified.

| Field | Status | Rationale |
|---|---|---|
| `category` | ✅ Spec | Enum: `tech`, `economics`, `politics`. Absent → general news. |
| `topic` | ➕ Extension | Free-text search. Allows users to combine topic + category (e.g. `"AI regulation" + "tech"`). The original spec only accepted `category`; adding `topic` extends coverage without breaking the existing contract. |
| `utc_offset_minutes` | ➕ Extension | Fix for timezone date drift (BUG-002). The client detects its local UTC offset and sends it so the backend computes `start_date`/`end_date` in the user's timezone rather than server UTC. Without this, users near midnight in UTC-offset timezones would get a misaligned 2-day window. |

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

## ADR-012 — Timezone-Aware Date Range

**Decision:** The frontend detects the client's UTC offset (`datetime.now().astimezone().utcoffset()`) and sends it as `utc_offset_minutes` in the request. The backend converts UTC now to the user's local timezone before computing `start_date` / `end_date`.

**Reason:** Using `datetime.now(UTC).date()` on the server produced date drift late at night — at 23:00 BRT the server was already on the next UTC day, shifting the 2-day window forward by one day. Client-side offset detection is exact for local deployments; cloud deployments would need browser JS for the same effect.

---

## ADR-013 — Markdown Invariant on `summary`

**Decision:** `NewsResponse` validates that `summary` contains at least one blank line (`\n\n`), enforcing multi-paragraph structure.

**Reason:** The frontend renders `summary` via `st.markdown()`. A single-blob paragraph offers no structure for the reader. The blank-line check is the minimal proxy for "formatted markdown" without over-constraining the LLM output. The system prompt instructs explicit paragraph separation to satisfy this invariant.

**Risk:** If the LLM returns a single paragraph despite the prompt, the API raises a 422-style validation error surfaced as HTTP 502. Mitigated by the prompt constraint and fallback chain.

---

## ADR-014 — Latency Optimisations

**Decision:**
- `max_tokens`: 4096 → 2048
- `TavilySearch.max_results`: 5 → 3
- `TavilySearch.search_depth`: `"advanced"` → `"basic"`
- `model_kwargs={"parallel_tool_calls": True}`

**Reason:** The dominant latency contributor is LLM generation time. Halving `max_tokens` is the highest-leverage cut — a news summary does not need 4096 tokens. `search_depth="basic"` removes deep page crawling, saving 1–3 s per Tavily query. `max_results=3` reduces the context fed to the LLM. `parallel_tool_calls` lets the model dispatch multiple Tavily queries simultaneously when the provider supports it; it is a no-op otherwise.

---

## ADR-015 — Windows `SelectorEventLoop` Policy

**Decision:** On `sys.platform == "win32"`, set `asyncio.WindowsSelectorEventLoopPolicy()` before the event loop is created.

**Reason:** Python's default `ProactorEventLoop` on Windows raises `ConnectionResetError (WinError 10054)` in `_call_connection_lost` whenever a client disconnects before the server finishes tearing down the transport. This is cosmetic — it does not affect correctness — but pollutes uvicorn logs on every request. `SelectorEventLoop` silences it the same way Linux does.

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
| Markdown Invariant | `NewsResponse.summary` validator | Guarantees structured output |

---

## I/O Contracts

### Request — `POST /news`

```json
{ "category": "tech", "topic": "artificial intelligence", "utc_offset_minutes": -180 }
```

All fields optional. `category` values: `tech`, `economics`, `politics`. Absent → general news.

### Response

```json
{
  "summary": "First paragraph...\n\nSecond paragraph...",
  "sources": ["https://..."]
}
```

**Pydantic invariants:**
- `summary`: min 1 char, contains `\n\n` (multi-paragraph markdown)
- `sources`: max 5 items, all prefixed with `https://`
