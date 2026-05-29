## Design: Unit of Work — DB Write Resilience in Stage 4

### Current Problem

`save_analysis_results()` in `repository.py` executes all INSERTs in a single loop and calls `db.commit()` once at the end. A single `aiosqlite.Error` on any ticker's INSERT propagates as an unhandled exception through `orchestrator.py`, aborting the entire run and returning HTTP 500 to the frontend — even if 9 out of 10 tickers wrote successfully.

### Solution: Per-row try/except in save_analysis_results

Change `save_analysis_results()` signature to return per-row errors instead of `None`:

```python
async def save_analysis_results(
    rows: list[dict], user_id: str = DEFAULT_USER_ID
) -> list[dict]:   # returns list of {"ticker": ..., "error_message": ...}
```

Inside the loop, wrap each INSERT individually:

```python
write_errors = []
for row in rows:
    try:
        await db.execute("INSERT INTO analysis_results ...", (...))
        await db.commit()          # commit per row — each row is its own transaction
    except aiosqlite.Error as e:
        logger.error("DB write failed for %s: %s", row.get("ticker"), e)
        write_errors.append({"ticker": row.get("ticker", "unknown"), "error_message": str(e)})
return write_errors
```

Committing per-row (instead of once at the end) means each successfully-written ticker is immediately durable, even if a later row fails.

### Orchestrator integration

`orchestrator.py` collects the returned write errors and merges them into `errors[]`:

```python
write_errors = await save_analysis_results(db_rows)
errors.extend(write_errors)
```

The `AnalysisResult` already carries `errors: list[dict]` — no model changes needed.

### HTTP response behavior

The existing API route (`POST /api/analysis/run`) already returns the `AnalysisResult` JSON. With this change:
- All tickers fail → HTTP 200, `assets=[]`, `top_5=[]`, `errors` non-empty
- Some tickers fail → HTTP 200, partial `assets`, `errors` non-empty
- No change to the API surface — `errors[]` was already in the response schema

### What does NOT change

- `AnalysisResult` model — no new fields
- API endpoint — no route or status-code changes
- Stages 1–3 error handling — already correct
- Frontend — already renders `errors` if present
