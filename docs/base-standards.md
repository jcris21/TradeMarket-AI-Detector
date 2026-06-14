
# FinAlly — base development standards

## Project context
Name: FinAlly — AI Trading Workstation
Domain: AI-powered simulated trading with LLM chat assistant
Stack: FastAPI (Python 3.12 / uv) + Next.js (TypeScript) + SQLite + LiteLLM → OpenRouter
Container: Single Docker container port 8000 (Next.js static export served by FastAPI)
AI inference: LiteLLM → OpenRouter → Cerebras (structured outputs via Pydantic v2)
Market data: GBM simulator (default) or Massive/Polygon.io (optional)

## Core principles
1. Spec before code — proposal in openspec/changes/ before any implementation
2. Small tasks — one task at a time, never skip steps
3. TDD — failing tests first (pytest-asyncio backend, Playwright E2E)
4. Type safety — Pydantic v2 all API I/O, TypeScript strict mode frontend
5. English only — all code, comments, docstrings, commits
6. 90%+ test coverage on backend (pytest-cov)
7. Incremental changes — one concern per commit

## Language & runtime
- Backend: Python 3.12, uv package manager (never bare pip)
- Frontend: TypeScript 5+, Next.js static export
- Backend linter: ruff (line-length 100, target py312)
- Test runner: pytest + pytest-asyncio (asyncio_mode = auto)

## Architecture decisions
- FastAPI serves API (/api/*) AND static Next.js build (/**)
- SSE streaming for live price ticks — never WebSockets
- SQLite via aiosqlite — no ORM, raw parameterized SQL
- All LLM calls through app/llm.py — never call litellm directly from routes
- LLM_MOCK=true for tests (deterministic, no API cost)
- AI trade orders validated by Pydantic before execution

## References
- docs/backend-standards.md — FastAPI, uv, aiosqlite, LiteLLM
- docs/frontend-standards.md — Next.js, Tailwind, SSE, Recharts
- docs/api-spec.yml — endpoint contracts
- docs/data-model.md — SQLite schema and domain entities