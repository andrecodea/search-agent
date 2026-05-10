# Known Bugs & Fixes

---

## BUG-001 — `TypeError: unhashable type: 'Settings'`

**Symptom:** `POST /news` returned `500 Internal Server Error` on every request.

**Traceback:**
```
File "app/main.py", in get_news_agent
    return build_news_agent(settings)
TypeError: unhashable type: 'Settings'
```

**Cause:** `build_news_agent(settings: Settings)` used `@lru_cache`, which requires all arguments to be hashable (used as cache keys). `Settings` is a subclass of `BaseSettings` (Pydantic), which does not implement `__hash__`.

**Fix:** Remove the `settings` parameter from `build_news_agent`. The function now calls `get_settings()` internally — which is already `@lru_cache` and always returns the same instance.

```python
# Before
@lru_cache
def build_news_agent(settings: Settings) -> NewspaperAgent:
    return NewspaperAgent(settings)

def get_news_agent(settings: Settings = Depends(get_settings)) -> NewsAgentProtocol:
    return build_news_agent(settings)

# After
@lru_cache
def build_news_agent() -> NewspaperAgent:
    return NewspaperAgent(get_settings())

def get_news_agent() -> NewsAgentProtocol:
    return build_news_agent()
```

**File:** `app/main.py`

---

## BUG-002 — Tavily date range shifted by timezone

**Symptom:** With local time near midnight (Brazil, UTC-3), Tavily returned results from a date range shifted one day ahead. For example, at 23:00 BRT on day 8, the range appeared as day 7–9 instead of day 6–8.

**Cause:** `datetime.now(UTC)` was already on day 9 UTC while the local user was still on day 8. Truncating with `.date()` gives the UTC date, not the local one. With `timedelta(days=2)`, `start_date` landed on day 7 and `end_date` on day 9 — correct in UTC, wrong from the user's perspective.

**Fix:** The frontend detects the local machine's UTC offset (`datetime.now().astimezone().utcoffset()`) and sends it as `utc_offset_minutes` in the payload. The backend converts `now(UTC)` to the user's timezone and computes `start_date`/`end_date` in local time — no buffer, no ambiguity.

```python
# Frontend (news.py) — detects offset once on page load
_UTC_OFFSET_MINUTES = int(datetime.now().astimezone().utcoffset().total_seconds() / 60)
# e.g. Brazil (UTC-3) → -180

# Backend (agent.py) — exact dates in the user's timezone
user_tz = timezone(timedelta(minutes=utc_offset_minutes))
now_local = datetime.now(UTC).astimezone(user_tz)
tavily_start = (now_local - timedelta(days=2)).date().isoformat()  # "2026-05-06" in BRT
tavily_end   = now_local.date().isoformat()                         # "2026-05-08" in BRT
```

Works correctly for local deployments. For cloud deployments, the frontend would need browser-side JavaScript detection (browser offset, not server offset).

**Files:** `app/schemas.py`, `app/agent.py`, `app/main.py`, `frontend/pages/news.py`

**Validation (`tests/test_date_range.py`):**

The date logic was extracted into `_compute_date_range(utc_offset_minutes, now)` — a pure function that accepts a fixed `now`, making tests deterministic. A suite of 30 tests covers:

| Group | Tests | What it validates |
|---|---|---|
| Specific offsets | 6 | UTC, BRT (-180), IST (+330), JST (+540), NZST (+720), midday UTC |
| Structural invariant | 18 (6 offsets × 3) | range = exactly 2 days; start < end; `now_local` within range |
| `NewsResponse` | 6 | accepts ≤5 sources; rejects 6+; rejects `http://`; rejects empty summary |

Concrete case that triggered the bug — BRT at 23:00 on day 8, UTC already on day 9:

```
_UTC_NOW = datetime(2026, 5, 9, 2, 0, 0, tzinfo=UTC)  # = 23:00 BRT on day 8

utc_offset_minutes=0    → start=2026-05-07  end=2026-05-09  ✅ correct in UTC
utc_offset_minutes=-180 → start=2026-05-06  end=2026-05-08  ✅ correct in BRT
```

---

## BUG-003 — `GET /` and `GET /favicon.ico` returned 404

**Symptom:** The browser generated two 404s in the uvicorn log when opening `http://localhost:8000` directly.

```
GET / HTTP/1.1" 404 Not Found
GET /favicon.ico HTTP/1.1" 404 Not Found
```

**Cause:** The API only defines `POST /news`. Browsers always attempt to load `/` and the favicon automatically.

**Fix:** Add two utility routes excluded from the Swagger schema:

```python
@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")

@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=204)
```

**File:** `app/main.py`

---

## BUG-004 — `ConnectionResetError: [WinError 10054]` in uvicorn logs

**Symptom:** After every completed request, uvicorn printed to the console:

```
Exception in callback _ProactorBasePipeTransport._call_connection_lost()
...
ConnectionResetError: [WinError 10054] An existing connection was forcibly closed by the remote host
```

**Cause:** The `ProactorEventLoop` (default on Windows since Python 3.8) raises `ConnectionResetError` when the client closes the connection before the server finishes tearing down the transport. On Linux, the equivalent is silenced by the `SelectorEventLoop`. The error is cosmetic — it does not affect the response or application state.

**Fix:** Switch to `WindowsSelectorEventLoopPolicy` on Windows before the event loop is created:

```python
import asyncio, sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
```

The `SelectorEventLoop` handles client disconnects the same way Linux does — no exception in the cleanup callback.

**File:** `app/main.py`

---

## BUG-005 — `save_to_history` could fail the response on disk errors

**Symptom:** If the disk was full or `history/` had a permission error, `POST /news` returned HTTP 500 to the client — even though the agent had already produced a valid response.

**Cause:** `save_to_history()` was called without exception handling in the endpoint. Any I/O error propagated through FastAPI's stack and produced a 500, discarding an otherwise successful agent response.

**Fix:** Wrap the call in `try/except` with `logger.exception` — the failure is logged, but the already-computed response is returned normally to the client.

```python
try:
    save_to_history(response, category, topic)
except Exception:
    logger.exception("Failed to save history entry — response already sent to client")
```

**File:** `app/main.py`

**Established pattern:** Secondary persistence operations (history, audit, cache) must never block the primary response. Isolate them in `try/except` and log the failure — the client should not pay for an error in an operation that is not part of the API contract.
