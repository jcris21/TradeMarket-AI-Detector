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
  rank: number | null;
  analyzed_at?: string;
  expected_gain_per10?: number | null;
  expected_loss_per10?: number | null;
  expected_value_per10?: number | null;
  hit_rate_used?: number | null;
  hit_rate_source?: string | null;
}

/** Response from POST /api/analysis/run */
export interface AnalysisRunResponse {
  run_id: string;
  analyzed_at: string;
  duration_seconds: number;
  top_5: AssetAnalysis[];
  assets: AssetAnalysis[];
  errors: Array<{ ticker: string; error_message: string }>;
}

/** Response from GET /api/analysis/latest */
export interface AnalysisLatestResponse {
  results: AssetAnalysis[];
}
