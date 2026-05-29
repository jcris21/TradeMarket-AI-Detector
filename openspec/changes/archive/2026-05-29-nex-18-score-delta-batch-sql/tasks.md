## Implementation Tasks — NEX-18 / TECH-003

### 1. Model

- [x] 1.1 Add `score_delta: float | None = None` to `AssetAnalysis` in `backend/app/analysis/models.py`
- [x] 1.2 Add `"score_delta": self.score_delta` to `AssetAnalysis.to_db_row()`

### 2. Database

- [x] 2.1 Add `("score_delta", "REAL")` to `_BET_SIZE_COLUMNS` in `backend/app/db/connection.py` for lazy migration
- [x] 2.2 Narrow migration exception to `aiosqlite.OperationalError` with `"duplicate column name"` check
- [x] 2.3 Add `score_delta` to INSERT in `backend/app/db/repository.py`

### 3. ScoringAgent

- [x] 3.1 Add `_get_prior_scores(db) -> dict[str, float]` to `backend/app/analysis/scoring_agent.py` — batch query using `GROUP BY run_id ORDER BY MAX(analyzed_at) DESC LIMIT 1 OFFSET 1`
- [x] 3.2 Add `prior_scores: dict[str, float] | None = None` parameter to `score_and_rank()`
- [x] 3.3 Compute `delta = round(s - _prior.get(asset.ticker, s), 2)` inside loop and set `score_delta` on each asset

### 4. Orchestrator

- [x] 4.1 Call `prior_scores = await _get_prior_scores(db)` in Stage 4, reusing existing DB connection
- [x] 4.2 Pass `prior_scores=prior_scores` to `score_and_rank()`

### 5. Tests

- [x] 5.1 `test_score_delta_between_runs` — correct delta from prior run scores
- [x] 5.2 `test_score_delta_first_run` — delta = 0.0 when no prior run in DB
- [x] 5.3 `test_score_delta_db_error` — DB error → prior_scores = {} → delta = 0.0
