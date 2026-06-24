/** Price update from SSE stream */
export interface PriceUpdate {
  ticker: string;
  price: number;
  previous_price: number;
  timestamp: number;
  change: number;
  change_percent: number;
  direction: "up" | "down" | "flat";
}

/** Map of ticker -> PriceUpdate from SSE */
export type PriceMap = Record<string, PriceUpdate>;

/** Portfolio position */
export interface Position {
  ticker: string;
  quantity: number;
  avg_cost: number;
  current_price: number;
  unrealized_pnl: number;
  pnl_percent: number;
  market_value: number;
}

/** Portfolio response from GET /api/portfolio */
export interface Portfolio {
  cash_balance: number;
  total_value: number;
  positions: Position[];
}

/** Trade request body for POST /api/portfolio/trade */
export interface TradeRequest {
  ticker: string;
  quantity: number;
  side: "buy" | "sell";
}

/** Trade response */
export interface TradeResponse {
  id: string;
  ticker: string;
  side: "buy" | "sell";
  quantity: number;
  price: number;
  executed_at: string;
}

/** Watchlist item from GET /api/watchlist */
export interface WatchlistItem {
  ticker: string;
  price?: number;
  previous_price?: number;
  change?: number;
  change_percent?: number;
  direction?: "up" | "down" | "flat";
}

/** Portfolio snapshot for P&L chart */
export interface PortfolioSnapshot {
  total_value: number;
  recorded_at: string;
}

/** Chat message */
export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  actions?: ChatActions | null;
  created_at: string;
}

/** Actions the LLM took */
export interface ChatActions {
  trades?: TradeResponse[];
  watchlist_changes?: { ticker: string; action: "add" | "remove" }[];
  errors?: string[];
}

/** Chat request body */
export interface ChatRequest {
  message: string;
}

/** Chat response from POST /api/chat */
export interface ChatResponse {
  message: ChatMessage;
}

/** Connection status for SSE */
export type ConnectionStatus = "connected" | "connecting" | "disconnected";

/** Technical analysis signal */
export type AnalysisSignal = "BUY" | "WAIT" | "AVOID";

/** Signal freshness state derived at read time from analyzed_at */
export type FreshnessStatus = "fresh" | "active" | "aged" | "expired";

/** Single asset analysis result */
export interface AssetAnalysis {
  ticker: string;
  signal: AnalysisSignal;
  confidence: number;
  entry_price: number;
  target_price: number;
  stop_loss: number;
  risk_reward_ratio: number;
  support_validated: boolean;
  indicators_summary: Record<string, unknown>;
  argument: string;
  score: number | null;
  score_quant?: number | null;
  score_legacy?: number | null;
  enrichment_delta?: number | null;
  enrichment_type?: "trader_chart" | "auto_screenshot" | null;
  score_enriched?: number | null;
  rank: number | null;
  rank_exclusion_reason?: string | null;
  analyzed_at?: string;
  freshness_status?: FreshnessStatus;
  freshness_age_hours?: number;
  expected_gain_per10?: number | null;
  expected_loss_per10?: number | null;
  expected_value_per10?: number | null;
  hit_rate_used?: number | null;
  hit_rate_source?: string | null;
  outcome?: "TARGET_HIT" | "STOP_HIT" | "EXPIRED" | null;
  atr_14_pct?: number | null;
  stop_viable?: boolean | null;
  is_stale?: boolean;
}

/** Response from POST /api/analysis/run (202 Accepted) */
export interface AnalysisRunResponse {
  run_id: string;
  tickers_total: number;
  started_at: string;
}

/** Pipeline stage of an async analysis run (US-204) */
export type RunStage = "data" | "scoring" | "complete" | "failed";

/** Response from GET /api/analysis/run/{run_id}/status (US-204) */
export interface RunStatus {
  run_id: string;
  stage: RunStage;
  tickers_total: number;
  tickers_completed: number;
  errors_so_far: Array<{ ticker: string; error_message: string; reason?: string }>;
  started_at: string;
  completed_at: string | null;
  estimated_remaining_seconds: number | null;
}

/** Response from GET /api/analysis/latest */
export interface AnalysisLatestResponse {
  results: AssetAnalysis[];
}

/** Response from GET /api/analysis/latest?partial=true (US-204) */
export interface AnalysisPartialResponse {
  results: AssetAnalysis[];
  partial: boolean;
}

/** Extracted support/resistance level from trader chart upload */
export interface ExtractedLevel {
  type: "support" | "resistance";
  price: number;
  confidence: number;
}

/** Response from POST /api/analysis/enrich/{ticker} with enrichment_type: trader_chart */
export interface TraderChartEnrichResponse {
  enrichment_id: string;
  extracted_levels: ExtractedLevel[];
  status: string;
}

/** Response from POST /api/analysis/enrich/{ticker}/confirm */
export interface LevelConfirmResult {
  custom_levels_applied: number;
  enrichment_delta: number;
  score_quant: number;
  score_enriched: number;
}

export interface SegmentPerformance {
  total: number;
  hit_ratio: number | null;
  profit_factor: number | null;
  realized_rr: number | null;
}

/** Performance summary from GET /api/analysis/performance */
export interface PerformanceSummary {
  phase_gate_active: boolean;
  phase: number;
  phase_banner: string;
  calibration_count: number;
  total_signals: number;
  target_hits: number;
  stop_hits: number;
  expired: number;
  orphaned_count: number;
  hit_ratio: number | null;
  profit_factor: number | null;
  realized_rr: number | null;
  hr_status: "green" | "red" | "neutral" | null;
  pf_status: "green" | "red" | null;
  rr_status: "green" | null;
  below_breakeven: boolean;
  b2_enriched?: SegmentPerformance | null;
  non_enriched?: SegmentPerformance | null;
}
