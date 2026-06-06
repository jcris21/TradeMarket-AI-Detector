## Design: Batch SQL for score_delta

### New function: `_get_prior_scores(db)`

Single async function in `scoring_agent.py` that queries the second-most-recent run:

```sql
SELECT ticker, score FROM analysis_results
WHERE run_id = (
  SELECT run_id FROM analysis_results
  GROUP BY run_id ORDER BY MAX(analyzed_at) DESC LIMIT 1 OFFSET 1
)
```

Uses `GROUP BY run_id` (not raw `ORDER BY analyzed_at`) to avoid timestamp ties within the same run. Returns `{}` on first run or `aiosqlite.OperationalError`.

### Updated: `score_and_rank(prior_scores)`

Accepts optional `prior_scores: dict[str, float] | None`. Inside the loop:

```python
delta = round(s - _prior.get(asset.ticker, s), 2)  # 0.0 for new/first-run tickers
```

### Orchestrator (Stage 4)

Reuses the existing DB connection opened for `_get_hit_rate`:

```python
db = await get_connection()
try:
    hit_rate, hit_rate_source = await _get_hit_rate(db)
    prior_scores = await _get_prior_scores(db)
finally:
    await db.close()
```

### Schema changes

- `score_delta REAL` added to `_BET_SIZE_COLUMNS` lazy migration list
- `score_delta` added to `AssetAnalysis.to_db_row()` and `repository.py` INSERT
- Migration uses `except aiosqlite.OperationalError as e: if "duplicate column name" not in str(e): raise`
