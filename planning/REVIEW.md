# FinAlly Project — Comprehensive Code Review

**Reviewed:** 2026-04-07
**Reviewer:** Claude Sonnet 4.6
**Scope:** Full codebase audit against PLAN.md specification

---

## Executive Summary

The market data subsystem (`backend/app/market/`) is complete, well-tested, and production-quality. Everything else specified in PLAN.md is entirely absent. There is no frontend, no FastAPI main application entry point, no database layer, no portfolio or watchlist API, no LLM chat integration, no Dockerfile, no start/stop scripts, no E2E test infrastructure, and no `.env.example`. The project is approximately 15% complete relative to the plan.

---

## 1. What Has Been Built vs. What Is Missing

### BUILT — Market Data Subsystem (backend/app/market/)

| Component | Status |
|---|---|
| `PriceUpdate` immutable dataclass | Complete |
| `PriceCache` thread-safe store | Complete |
| `MarketDataSource` abstract interface | Complete |
| `GBMSimulator` with Cholesky-correlated moves | Complete |
| `SimulatorDataSource` background task | Complete |
| `MassiveDataSource` Polygon.io REST poller | Complete |
| `create_market_data_source` factory | Complete |
| `create_stream_router` SSE endpoint | Complete (with one bug — see section 4) |
| 73 unit/integration tests (84% coverage) | Complete |
| Rich terminal demo (`market_data_demo.py`) | Complete |

### MISSING — Everything Else

| Component | Plan Section | Status |
|---|---|---|
| FastAPI main app (`main.py`) with startup/shutdown lifespan | §3, §6 | Not started |
| SQLite database init and schema (6 tables) | §7 | Not started |
| `GET /api/portfolio` | §8 | Not started |
| `POST /api/portfolio/trade` | §8 | Not started |
| `GET /api/portfolio/history` | §8 | Not started |
| `GET /api/watchlist` | §8 | Not started |
| `POST /api/watchlist` | §8 | Not started |
| `DELETE /api/watchlist/{ticker}` | §8 | Not started |
| `POST /api/chat` | §8 | Not started |
| `GET /api/health` | §8 | Not started |
| Portfolio snapshot background task (every 30s) | §7 | Not started |
| LiteLLM/OpenRouter chat integration | §9 | Not started |
| LLM mock mode (`LLM_MOCK=true`) | §9, §12 | Not started |
| `frontend/` Next.js project | §10 | Not started |
| Watchlist UI panel with sparklines | §10 | Not started |
| Main chart area | §10 | Not started |
| Portfolio heatmap (treemap) | §10 | Not started |
| P&L chart | §10 | Not started |
| Positions table | §10 | Not started |
| Trade bar (buy/sell) | §10 | Not started |
| AI chat panel | §10 | Not started |
| SSE `EventSource` connection with price flashing | §10 | Not started |
| `Dockerfile` (multi-stage Node + Python) | §11 | Not started |
| `docker-compose.yml` | §11 | Not started |
| `scripts/start_mac.sh` | §11 | Not started |
| `scripts/stop_mac.sh` | §11 | Not started |
| `scripts/start_windows.ps1` | §11 | Not started |
| `scripts/stop_windows.ps1` | §11 | Not started |
| `test/` Playwright E2E tests | §12 | Not started |
| `test/docker-compose.test.yml` | §12 | Not started |
| `.env.example` | §5 | Not started |
| `.gitignore` | §4 | Missing |
| `db/.gitkeep` | §4 | Present (directory exists) |

The `db/` directory exists but the `scripts/` directory does not. The `test/` directory exists but is empty.

---

## 2. Architecture and Plan Adherence

### What Is Correct

The market data subsystem follows the plan precisely:
- Strategy pattern with `MarketDataSource` ABC is implemented exactly as specified in §6.
- `PriceCache` as the single point of truth with version-based SSE change detection matches §6.
- `SimulatorDataSource` uses GBM with Cholesky-decomposed sector correlations as specified.
- The `MassiveDataSource` runs the synchronous REST call in `asyncio.to_thread()` to avoid blocking the event loop — this is correct and important.
- The factory reads `MASSIVE_API_KEY` from the environment exactly as specified.
- The SSE endpoint emits data in the `{ticker: {PriceUpdate dict}}` format described in §6.

### Structural Issue in `stream.py`

The `router` object is defined at module level (line 17) but is mutated inside `create_stream_router()` by registering a route on it each time the factory is called. If `create_stream_router()` is called more than once (e.g., during testing), the route is registered on the same `router` instance multiple times, causing duplicate routes in FastAPI. The `router` should be created inside the factory function, not at module level.

Current code:
```python
router = APIRouter(prefix="/api/stream", tags=["streaming"])   # module-level

def create_stream_router(price_cache: PriceCache) -> APIRouter:
    @router.get("/prices")                                      # mutates module-level router
    async def stream_prices(request: Request) -> StreamingResponse:
        ...
    return router
```

Fix: move `router = APIRouter(...)` to inside `create_stream_router()`.

### Missing Dependencies in `pyproject.toml`

The plan requires several components that have no corresponding Python packages in `pyproject.toml`:

| Missing Dependency | Required For |
|---|---|
| `litellm` | LLM chat integration (§9) |
| `aiosqlite` or `sqlite3` wrapper | Database layer (§7) |
| `python-dotenv` | Loading `.env` on startup |

The `litellm` package is specifically named in the plan (§9). Without it being listed, the backend cannot be built for the chat feature.

---

## 3. Code Quality Assessment (Market Data Subsystem)

Overall quality is high. The following observations apply to the completed code.

### Strengths

- Immutability is consistently applied: `PriceUpdate` uses `@dataclass(frozen=True, slots=True)`.
- Thread safety in `PriceCache` is correct — all public methods acquire the lock before accessing `_prices`.
- The `GBMSimulator` separates concerns cleanly: math is in `GBMSimulator`, async lifecycle is in `SimulatorDataSource`.
- Error handling in both `SimulatorDataSource._run_loop()` and `MassiveDataSource._poll_once()` catches exceptions and logs them without crashing the background task — the correct behavior for a long-running service.
- The `asyncio.to_thread()` call in `MassiveDataSource._poll_once()` correctly offloads the blocking synchronous Massive SDK call.
- Test coverage is genuine — tests cover edge cases (zero previous price, malformed snapshots, duplicate ticker add, empty ticker list, exception resilience).

### Issues

**MEDIUM — `version` property is not thread-safe for read**

In `PriceCache`, `_version` is incremented under the lock in `update()`, but the `version` property reads `_version` without acquiring the lock:

```python
@property
def version(self) -> int:
    return self._version   # no lock
```

In CPython this is safe in practice due to the GIL, but it is not guaranteed by the Python memory model and will fail under alternative interpreters (PyPy with STM, GraalPy). The lock should be acquired for the read, or `version` should be read atomically via `threading.atomic` equivalent patterns.

**LOW — `DEFAULT_PARAMS` is mutable and could be mutated by callers**

In `seed_prices.py`, `DEFAULT_PARAMS` is a plain `dict`. In `simulator.py` line 152, it is copied via `dict(DEFAULT_PARAMS)`, which is correct. However, the module-level constant being mutable is an unnecessary risk if any future code accesses it directly. Consider using a `types.MappingProxyType` or `frozenset`-style constant.

**LOW — `TSLA` is listed in the `tech` correlation group but short-circuited before the group check**

In `seed_prices.py`, `CORRELATION_GROUPS["tech"]` includes `TSLA`. In `simulator.py`, the `_pairwise_correlation` method checks `if t1 == "TSLA" or t2 == "TSLA": return TSLA_CORR` before ever checking group membership. The result is correct, but the presence of TSLA in the `tech` set is misleading — it suggests group membership matters for TSLA when it does not. Remove TSLA from `CORRELATION_GROUPS["tech"]` to make the data consistent with the logic.

**LOW — `test_models.py` line 69: expected `change_percent` comment is wrong**

The comment `# (0.50 / 190.00) * 100` gives `0.2631...` but the assertion is `0.2632`. The actual computation is `round((190.50 - 190.00) / 190.00 * 100, 4) = 0.2632`. The comment is slightly misleading — it omits that the price used is `previous_price` (190.00), not `price` (190.50). The assertion is numerically correct; only the comment is imprecise.

**LOW — `conftest.py` fixture `event_loop_policy` does nothing useful**

The fixture returns a policy object but does not set it on the event loop. `pytest-asyncio` with `asyncio_mode = "auto"` does not consume a fixture named `event_loop_policy` this way. This is dead code.

---

## 4. Bugs

### BUG (MEDIUM) — `stream.py` module-level router causes duplicate route registration

Described in section 2. Calling `create_stream_router()` twice appends the `GET /api/stream/prices` handler to the same router instance each time, resulting in duplicate routes. This is a latent bug that will surface during integration testing when a FastAPI app is created in a test and `create_stream_router()` is called more than once across the test session.

### BUG (LOW) — `SimulatorDataSource` does not normalize ticker case

`MassiveDataSource.add_ticker()` normalizes to uppercase via `.upper().strip()`. `SimulatorDataSource.add_ticker()` does not — it passes the ticker directly to `GBMSimulator.add_ticker()`. If a user adds `"aapl"` via the (future) watchlist API, the simulator will create a separate entry from `"AAPL"`, breaking price lookups. Normalization should happen at the `MarketDataSource` interface level or consistently in both implementations.

---

## 5. Security Observations

The completed code has no security issues because it has no user-facing input paths yet. The following pre-emptive notes apply to future development:

- **Ticker input validation** is absent in `SimulatorDataSource` (as noted above). The future watchlist `POST /api/watchlist` endpoint must validate and normalize ticker symbols (uppercase, alphanumeric, length limit) before passing them to the market data source or storing them in the database.
- **No `.env.example` committed.** The plan requires one (§5). Without it, there is no documented contract for required secrets, and contributors may run the app without `OPENROUTER_API_KEY`, getting cryptic failures at the LLM call site rather than at startup.
- **`OPENROUTER_API_KEY` validation at startup** is not yet implemented (no main app exists). When the main app is built, it should validate the presence of required secrets at startup, not at first request.
- **No rate limiting** on any API endpoint (none exist yet). The future `POST /api/portfolio/trade` and `POST /api/chat` endpoints should have rate limiting to prevent runaway LLM costs and trade flooding in a demo environment.

---

## 6. Backend API Completeness

Zero of nine planned API endpoints exist. The FastAPI application entry point (`main.py`) has not been created. There is no `app` object to mount routers on, no lifespan handler to start/stop the market data source, and no static file serving for the (non-existent) frontend build.

The completed `create_stream_router()` is ready to be mounted once a main app exists. All other routers (portfolio, watchlist, chat, health) need to be written.

---

## 7. Frontend Completeness

The `frontend/` directory does not exist. No Next.js project has been initialized. Zero of the ten UI components specified in §10 have been built.

---

## 8. Docker and Deployment

No `Dockerfile` exists. No `docker-compose.yml` exists. No start/stop scripts exist. The project cannot be run via the single Docker command described in the plan's first-launch experience (§2).

The `README.md` at the project root documents the intended `docker build` and `docker run` commands, but they will fail because the Dockerfile is missing.

---

## 9. Test Coverage

### Backend Tests (Completed)

- 73 tests across 6 modules, all in `backend/tests/market/`
- 84% overall coverage of `backend/app/market/`
- `test_massive.py` has 56% coverage of `massive_client.py` (acceptable — API methods are mocked by design)
- No tests for any other backend component (none exist yet)

### Missing Test Infrastructure

- No backend tests for: database layer, portfolio API, watchlist API, chat API, health endpoint, LLM integration, mock LLM mode
- No frontend tests (no frontend exists)
- `test/` directory at project root is empty — no Playwright E2E tests, no `docker-compose.test.yml`
- The plan's requirement (§12) for E2E coverage of all critical user flows is entirely unaddressed

---

## 10. Issues Raised in PLAN.md §13 That Remain Unresolved

The plan's own review notes (§13) identified 9 open questions and 5 feedback items. None have been resolved because the affected components have not been built. These must be resolved before implementation of those components begins:

1. **"Daily change %"** — the simulator has no concept of a previous close. Implementation must define whether sparkline/watchlist percentage is "change since page load" or "change since simulator start" and document the decision.
2. **SSE stream and dynamic watchlist** — whether adding a ticker mid-session automatically appears in the stream (it does in the current implementation — `add_ticker` on the source updates the cache, and the SSE stream reads from the cache) — but this should be verified end-to-end and documented.
3. **Positions in removed watchlist tickers** — no decision has been made. The SSE stream currently streams all tickers in the source, not just the watchlist. This must be reconciled with the database design.
4. **`portfolio_snapshots` retention** — no pruning logic defined. Must add a retention window (e.g., 7 days) when implementing the snapshot background task.
5. **Lazy init: startup vs. first request** — no decision made. Recommend startup init to avoid race conditions.
6. **"cerebras-inference skill" reference** — not present in the planning directory. The Backend Engineer needs the LiteLLM configuration (base URL, model ID, auth header format) before implementing the chat endpoint.
7. **Model identifier** — `openrouter/openai/gpt-oss-120b` should be verified as current and made configurable via `LLM_MODEL` env var.
8. **Conversation history window** — no limit defined. Must cap at a fixed message count (recommend 20) to prevent context overflow.
9. **LLM failure handling** — no fallback specified. Must define behavior for 429, 500, and structured output parse failures before implementing the chat endpoint.
10. **Mock LLM response payload** — not defined. The E2E test author and Backend Engineer must agree on the exact fixed response returned when `LLM_MOCK=true`.

---

## 11. Prioritized Recommendations

### Immediate (blockers for any further development)

1. Create `backend/app/main.py` with FastAPI app, lifespan handler (start/stop market data source, initialize database), and mount the `create_stream_router()` already built.
2. Create `.env.example` with all three variables (`OPENROUTER_API_KEY`, `MASSIVE_API_KEY`, `LLM_MOCK`) and explanatory comments.
3. Create `.gitignore` covering `.env`, `__pycache__`, `*.pyc`, `db/finally.db`, `.pytest_cache`, `node_modules`, `.next`, `out/`.
4. Add `litellm` and `python-dotenv` to `backend/pyproject.toml` dependencies (both are needed before the LLM and app startup work can begin).
5. Fix the module-level `router` bug in `backend/app/market/stream.py`.

### Short-term (before feature development)

6. Implement the SQLite database layer: schema creation, lazy init at startup, seed data insertion.
7. Normalize ticker case in `SimulatorDataSource.add_ticker()` to match `MassiveDataSource`.
8. Resolve the open questions from PLAN.md §13 (items 1, 3, 4, 5, 7, 8, 9, 10 above) and record decisions in the plan before building dependent components.
9. Initialize the Next.js frontend project (`npx create-next-app@latest frontend --typescript --tailwind --app`).
10. Create the `Dockerfile` (multi-stage).

### Medium-term (feature development order)

11. Implement watchlist, portfolio, and trade API endpoints (§8).
12. Implement portfolio snapshot background task with 7-day retention.
13. Implement LLM chat endpoint with structured outputs and mock mode.
14. Build the frontend: SSE connection, watchlist panel, chart area, portfolio visualizations, trade bar, chat panel.
15. Create start/stop scripts for macOS and Windows.
16. Create `test/docker-compose.test.yml` and Playwright E2E test suite.

### Low-priority fixes (in completed code)

17. Move `router = APIRouter(...)` inside `create_stream_router()` to prevent duplicate registration.
18. Acquire the lock in `PriceCache.version` property for strict thread safety correctness.
19. Remove TSLA from `CORRELATION_GROUPS["tech"]` in `seed_prices.py`.
20. Remove the dead `event_loop_policy` fixture from `backend/tests/conftest.py`.
