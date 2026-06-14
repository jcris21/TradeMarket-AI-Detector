# Backend standards — FinAlly FastAPI

## Package management
- Use uv exclusively: uv add , uv run pytest, uv run uvicorn
- Never bare pip install — bypasses lockfile
- Dev deps: uv add --dev 

## FastAPI patterns
- All route handlers must be async
- Use APIRouter per domain: routers/portfolio.py, routers/ai.py, routers/market.py
- Return Pydantic v2 models (model_config = ConfigDict(from_attributes=True))
- SSE: StreamingResponse with media_type="text/event-stream"
- HTTPException with correct status codes — never bare 500

## Database (aiosqlite)
- Lazy init — DB created on first request if not exists
- All queries parameterized — no f-string SQL ever
- Pattern: async with aiosqlite.connect(DB_PATH) as db: ...
- Schema changes: plain SQL files in db/migrations/ (no Alembic)
- Never blocking DB calls in async endpoints

## LiteLLM / AI integration
- All LLM calls go through app/llm.py ONLY
- Never import litellm directly in route files
- LLM_MOCK=true for all tests (set in pytest env or .env.test)
- Structured outputs: Pydantic schemas in app/schemas/ai.py
- Trade execution schema: ticker, action (buy/sell), quantity, reasoning
- Validate AI output with Pydantic before any trade execution

## Testing
- Tests in backend/tests/ as test_*.py
- asyncio_mode = auto (already in pyproject.toml)
- Run: uv run pytest --cov=app --cov-report=term-missing
- Target: 90%+ coverage on app/

## Code style
- ruff check . && ruff format . before every commit
- Type annotations on all functions
- Docstrings on all public functions