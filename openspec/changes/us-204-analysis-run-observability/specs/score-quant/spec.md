## MODIFIED Requirements

### Requirement: score_quant is the exclusive ranking key
`score_and_rank_with_errors()` SHALL sort qualifying assets by `score_quant` descending. `score_legacy` SHALL NOT influence sort order. Assets with `score_quant = None` SHALL be excluded from the ranked list.

The `POST /api/analysis/run` endpoint is the exclusive trigger for a scoring run. Its response shape is `{run_id: string, tickers_total: int, started_at: ISO8601}` (HTTP 202). Clients MUST poll `GET /api/analysis/run/{run_id}/status` to determine completion, then fetch results from `GET /api/analysis/latest`. **BREAKING**: prior behavior returning the full result synchronously from `POST /api/analysis/run` is removed.

#### Scenario: Ranking by score_quant
- **WHEN** two assets have `score_quant=80` and `score_quant=60`
- **THEN** the asset with `score_quant=80` ranks higher regardless of `score_legacy` values

#### Scenario: POST /api/analysis/run returns 202 not full result
- **WHEN** `POST /api/analysis/run` is called with a valid ticker list
- **THEN** the response is HTTP 202 with `run_id` — not the full analysis JSON
