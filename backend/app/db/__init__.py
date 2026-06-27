"""Database layer for FinAlly.

Public API:
    init_db              - Create tables and seed default data
    get_connection       - Get an async SQLite connection
    set_db_path          - Override DB file path (for testing)

    get_cash_balance     - Get user's cash balance
    update_cash_balance  - Set user's cash balance

    get_watchlist        - List watchlist tickers
    add_to_watchlist     - Add a ticker
    remove_from_watchlist - Remove a ticker

    get_positions        - List all positions
    get_position         - Get one position by ticker
    upsert_position      - Create or update a position
    delete_position      - Remove a position

    insert_trade         - Record a trade

    insert_snapshot      - Record a portfolio value snapshot
    get_portfolio_history - Get snapshot history

    insert_chat_message  - Store a chat message
    get_chat_history     - Get recent chat history

    get_analysis_tickers    - List tickers for analysis
    add_analysis_ticker     - Add a ticker to analysis list
    remove_analysis_ticker  - Remove a ticker from analysis list
    save_analysis_results   - Persist analysis results batch
    update_outcome_atomic   - Atomically write outcome for a signal (idempotent)
    update_enrichment_delta - Set post-hoc enrichment_delta for a ticker in a run
    get_latest_analysis     - Get most recent analysis run results
    get_analysis_by_ticker  - Get latest analysis for a specific ticker
    get_performance_summary - Compute aggregated outcome metrics
    get_prior_scores        - Get {ticker: score_quant} from the run before a given run_id

    create_enrichment_job              - Insert a new enrichment job row
    get_enrichment_job                 - Fetch an enrichment job by id
    update_enrichment_job              - Update status/delta/error on enrichment job
    set_ticker_preferred_url           - Save preferred_chart_url on analysis_tickers
    set_analysis_enrichment_status     - Update enrichment_status on analysis_results
    reset_stale_enrichments            - Mark pending/processing enrichments as failed on startup

    store_custom_levels                - Persist confirmed S/R levels with TTL
    load_active_custom_levels          - Fetch non-expired custom levels for a ticker
    expire_stale_levels                - NULL out expired custom_levels rows
    update_analysis_result_custom_levels - Update custom_levels_applied + enrichment_delta
"""

from .connection import get_connection, init_db, set_db_path
from .repository import (
    add_analysis_ticker,
    add_to_watchlist,
    create_enrichment_job,
    delete_position,
    expire_stale_levels,
    find_pending_enrichment_job,
    get_analysis_by_ticker,
    get_analysis_tickers,
    get_cash_balance,
    get_chat_history,
    get_enrichment_job,
    get_latest_analysis,
    get_performance_summary,
    get_portfolio_history,
    get_prior_scores,
    get_position,
    get_positions,
    get_watchlist,
    insert_chat_message,
    insert_snapshot,
    insert_trade,
    load_active_custom_levels,
    remove_analysis_ticker,
    remove_from_watchlist,
    reset_stale_enrichments,
    save_analysis_results,
    set_analysis_enrichment_status,
    set_ticker_preferred_url,
    store_custom_levels,
    update_analysis_result_custom_levels,
    update_cash_balance,
    update_enrichment_delta,
    update_enrichment_job,
    update_outcome_atomic,
    upsert_position,
)
from .schema import DEFAULT_CASH_BALANCE, DEFAULT_TICKERS, DEFAULT_USER_ID

__all__ = [
    "init_db",
    "get_connection",
    "set_db_path",
    "get_cash_balance",
    "update_cash_balance",
    "get_watchlist",
    "add_to_watchlist",
    "remove_from_watchlist",
    "get_positions",
    "get_position",
    "upsert_position",
    "delete_position",
    "insert_trade",
    "insert_snapshot",
    "get_portfolio_history",
    "insert_chat_message",
    "get_chat_history",
    "add_analysis_ticker",
    "get_analysis_tickers",
    "get_analysis_by_ticker",
    "get_latest_analysis",
    "get_prior_scores",
    "remove_analysis_ticker",
    "save_analysis_results",
    "update_outcome_atomic",
    "update_enrichment_delta",
    "get_performance_summary",
    "create_enrichment_job",
    "get_enrichment_job",
    "update_enrichment_job",
    "set_ticker_preferred_url",
    "reset_stale_enrichments",
    "set_analysis_enrichment_status",
    "store_custom_levels",
    "load_active_custom_levels",
    "expire_stale_levels",
    "find_pending_enrichment_job",
    "update_analysis_result_custom_levels",
    "DEFAULT_USER_ID",
    "DEFAULT_TICKERS",
    "DEFAULT_CASH_BALANCE",
]

