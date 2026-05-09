# Known Bugs & Fixes

---

## BUG-001 — `TypeError: unhashable type: 'Settings'`

**Sintoma:** `POST /news` retornava `500 Internal Server Error` em toda requisição.

**Traceback:**
```
File "app/main.py", in get_news_agent
    return build_news_agent(settings)
TypeError: unhashable type: 'Settings'
```

**Causa:** `build_news_agent(settings: Settings)` usava `@lru_cache`, que exige que todos os argumentos sejam hashable (usados como chave do cache). `Settings` é uma subclasse de `BaseSettings` (Pydantic), que não implementa `__hash__`.

**Fix:** Remover o parâmetro `settings` de `build_news_agent`. A função passa a chamar `get_settings()` internamente — que já é `@lru_cache` e retorna sempre a mesma instância.

```python
# Antes
@lru_cache
def build_news_agent(settings: Settings) -> NewspaperAgent:
    return NewspaperAgent(settings)

def get_news_agent(settings: Settings = Depends(get_settings)) -> NewsAgentProtocol:
    return build_news_agent(settings)

# Depois
@lru_cache
def build_news_agent() -> NewspaperAgent:
    return NewspaperAgent(get_settings())

def get_news_agent() -> NewsAgentProtocol:
    return build_news_agent()
```

**Arquivo:** `app/main.py`

---

## BUG-002 — Range de datas do Tavily deslocado por timezone

**Sintoma:** Com o horário local próximo da meia-noite (Brasil, UTC-3), o Tavily retornava resultados de um range adiantado em um dia. Por exemplo, às 23:00 BRT do dia 8, o range aparecia como dia 7–9 em vez de dia 6–8.

**Causa:** `datetime.now(UTC)` já estava no dia 9 UTC quando o usuário local ainda estava no dia 8. O cálculo `started_at.date()` trunca para a data UTC, não local. Com `timedelta(days=2)`, o `start_date` ficava dia 7 e o `end_date` dia 9 — correto em UTC, errado na perspectiva local.

**Fix (definitivo):** O frontend detecta o UTC offset da máquina local (`datetime.now().astimezone().utcoffset()`) e envia como `utc_offset_minutes` no payload. O backend converte `now(UTC)` para o timezone do usuário e computa `start_date`/`end_date` em horário local — sem buffer, sem ambiguidade.

```python
# Frontend (news.py) — detecta offset uma vez no carregamento da página
_UTC_OFFSET_MINUTES = int(datetime.now().astimezone().utcoffset().total_seconds() / 60)
# Ex: Brasil (UTC-3) → -180

# Backend (agent.py) — datas exatas no timezone do usuário
user_tz = timezone(timedelta(minutes=utc_offset_minutes))
now_local = datetime.now(UTC).astimezone(user_tz)
tavily_start = (now_local - timedelta(days=2)).date().isoformat()  # "2026-05-06" em BRT
tavily_end   = now_local.date().isoformat()                         # "2026-05-08" em BRT
```

Funciona corretamente para deployment local. Para deployment em cloud, o frontend precisaria de detecção via JavaScript (offset do browser, não do servidor).

**Arquivos:** `app/schemas.py`, `app/agent.py`, `app/main.py`, `frontend/pages/news.py`

**Validação (`tests/test_date_range.py`):**

A lógica de cálculo foi extraída para `_compute_date_range(utc_offset_minutes, now)` — função pura que aceita um `now` fixo, tornando os testes determinísticos. Bateria de 30 testes cobre:

| Grupo | Testes | O que valida |
|---|---|---|
| Offsets específicos | 6 | UTC, BRT (-180), IST (+330), JST (+540), NZST (+720), midday UTC |
| Invariante estrutural | 18 (6 offsets × 3) | range = exatamente 2 dias; start < end; `now_local` dentro do range |
| `NewsResponse` | 6 | aceita ≤5 fontes; rejeita 6+; rejeita `http://`; rejeita summary vazio |

Caso concreto que originou o bug — BRT às 23:00 do dia 8, UTC já no dia 9:

```
_UTC_NOW = datetime(2026, 5, 9, 2, 0, 0, tzinfo=UTC)  # = 23:00 BRT dia 8

utc_offset_minutes=0    → start=2026-05-07  end=2026-05-09  ✅ correto em UTC
utc_offset_minutes=-180 → start=2026-05-06  end=2026-05-08  ✅ correto em BRT
```

---

## BUG-003 — `GET /` e `GET /favicon.ico` retornavam 404

**Sintoma:** O browser gerava dois 404 no log do uvicorn ao abrir `http://localhost:8000` diretamente.

```
GET / HTTP/1.1" 404 Not Found
GET /favicon.ico HTTP/1.1" 404 Not Found
```

**Causa:** A API só define `POST /news`. O browser sempre tenta carregar `/` e o favicon automaticamente.

**Fix:** Adicionar duas rotas utilitárias sem aparecer no schema do Swagger:

```python
@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")

@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=204)
```

**Arquivo:** `app/main.py`

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

---

## BUG-004 — `ConnectionResetError: [WinError 10054]` no log do uvicorn

**Sintoma:** A cada requisição concluída, o uvicorn imprimia no console:

```
Exception in callback _ProactorBasePipeTransport._call_connection_lost()
...
ConnectionResetError: [WinError 10054] Foi forçado o cancelamento de uma conexão existente pelo host remoto
```

**Causa:** O `ProactorEventLoop` (padrão no Windows desde Python 3.8) levanta `ConnectionResetError` quando o cliente fecha a conexão antes do servidor terminar de limpar o transporte. No Linux, o equivalente é silenciado pelo `SelectorEventLoop`. O erro é cosmético — não afeta a resposta nem o estado da aplicação.

**Fix:** Trocar para `WindowsSelectorEventLoopPolicy` no Windows antes do event loop ser criado:

```python
import asyncio, sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
```

O `SelectorEventLoop` trata desconexões do cliente da mesma forma que o Linux — sem exceção no callback de cleanup.

**Arquivo:** `app/main.py`
