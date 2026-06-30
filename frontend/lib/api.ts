import type {
  Portfolio,
  TradeRequest,
  TradeResponse,
  WatchlistItem,
  PortfolioSnapshot,
  ChatResponse,
  ChatMessage,
  AnalysisRunResponse,
  AnalysisLatestResponse,
  AnalysisPartialResponse,
  RunStatus,
  AssetAnalysis,
  PerformanceSummary,
  TraderChartEnrichResponse,
  LevelConfirmResult,
} from "./types";

const BASE = "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status}: ${body}`);
  }
  return res.json();
}

export async function getPortfolio(): Promise<Portfolio> {
  const data = await request<{
    positions: Portfolio["positions"];
    cash: number;
    total_value: number;
  }>("/portfolio");
  return {
    positions: data.positions,
    cash_balance: data.cash,
    total_value: data.total_value,
  };
}

export async function executeTrade(trade: TradeRequest): Promise<TradeResponse> {
  const data = await request<{ trade: TradeResponse }>("/portfolio/trade", {
    method: "POST",
    body: JSON.stringify(trade),
  });
  return data.trade;
}

export async function getPortfolioHistory(): Promise<PortfolioSnapshot[]> {
  const data = await request<{ snapshots: PortfolioSnapshot[] }>("/portfolio/history");
  return data.snapshots;
}

export async function getWatchlist(): Promise<WatchlistItem[]> {
  const data = await request<{ watchlist: WatchlistItem[] }>("/watchlist");
  return data.watchlist;
}

export async function addToWatchlist(ticker: string): Promise<void> {
  await request("/watchlist", {
    method: "POST",
    body: JSON.stringify({ ticker }),
  });
}

export async function removeFromWatchlist(ticker: string): Promise<void> {
  await request(`/watchlist/${ticker}`, { method: "DELETE" });
}

export async function sendChatMessage(message: string): Promise<ChatResponse> {
  const data = await request<{
    message: string;
    trades: Array<{ ticker: string; side: string; quantity: number; price: number; status?: string; error?: string }>;
    watchlist_changes: Array<{ ticker: string; action: string; status?: string; error?: string }>;
  }>("/chat", {
    method: "POST",
    body: JSON.stringify({ message }),
  });

  const executedTrades = data.trades
    .filter((t) => t.status === "executed")
    .map((t) => ({
      id: crypto.randomUUID(),
      ticker: t.ticker,
      side: t.side as "buy" | "sell",
      quantity: t.quantity,
      price: t.price,
      executed_at: new Date().toISOString(),
    }));

  const errors = data.trades
    .filter((t) => t.error)
    .map((t) => t.error!);

  const assistantMessage: ChatMessage = {
    id: crypto.randomUUID(),
    role: "assistant",
    content: data.message,
    actions: {
      trades: executedTrades.length > 0 ? executedTrades : undefined,
      watchlist_changes: data.watchlist_changes.length > 0 ? data.watchlist_changes.map((w) => ({
        ticker: w.ticker,
        action: w.action as "add" | "remove",
      })) : undefined,
      errors: errors.length > 0 ? errors : undefined,
    },
    created_at: new Date().toISOString(),
  };

  return { message: assistantMessage };
}

export async function getHealth(): Promise<{ status: string }> {
  return request<{ status: string }>("/health");
}

export async function getTickerHistory(
  ticker: string,
  period = "3mo"
): Promise<{ ticker: string; period: string; data: { time: number; value: number }[] }> {
  return request(`/market/history/${ticker}?period=${period}`);
}

/** Error thrown when POST /api/analysis/run returns 409 (run already active). */
export class RunInProgressError extends Error {
  runId: string;
  constructor(runId: string) {
    super("run_already_in_progress");
    this.name = "RunInProgressError";
    this.runId = runId;
  }
}

export async function startAnalysisRun(tickers: string[]): Promise<AnalysisRunResponse> {
  const res = await fetch(`${BASE}/analysis/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tickers: tickers.length > 0 ? tickers : null }),
  });
  if (res.status === 409) {
    const body = await res.json();
    throw new RunInProgressError(body.run_id);
  }
  if (!res.ok) {
    throw new Error(`${res.status}: ${await res.text()}`);
  }
  return res.json();
}

export async function getRunStatus(runId: string): Promise<RunStatus> {
  return request<RunStatus>(`/analysis/run/${runId}/status`);
}

export async function getLatestPartial(): Promise<AnalysisPartialResponse> {
  return request<AnalysisPartialResponse>("/analysis/latest?partial=true");
}

export async function getLatestAnalysis(): Promise<AnalysisLatestResponse> {
  return request<AnalysisLatestResponse>("/analysis/latest");
}

export async function getTickerAnalysis(ticker: string): Promise<AssetAnalysis> {
  return request<AssetAnalysis>(`/analysis/${ticker}`);
}

export async function getAnalysisTickers(): Promise<{ tickers: string[] }> {
  return request<{ tickers: string[] }>("/analysis/tickers");
}

export async function addAnalysisTicker(ticker: string): Promise<void> {
  await request("/analysis/tickers", {
    method: "POST",
    body: JSON.stringify({ ticker }),
  });
}

export async function removeAnalysisTicker(ticker: string): Promise<void> {
  await request(`/analysis/tickers/${ticker}`, { method: "DELETE" });
}

export async function getPerformanceSummary(): Promise<PerformanceSummary> {
  return request<PerformanceSummary>("/analysis/performance");
}

export async function getOutcomesHistory(): Promise<AssetAnalysis[]> {
  const data = await request<{ outcomes: AssetAnalysis[]; total: number }>("/analysis/outcomes");
  return data.outcomes;
}

export async function enrichTraderChart(
  ticker: string,
  chartImageB64: string
): Promise<TraderChartEnrichResponse> {
  return request<TraderChartEnrichResponse>(`/analysis/${ticker}/enrich`, {
    method: "POST",
    body: JSON.stringify({ enrichment_type: "trader_chart", chart_image: chartImageB64 }),
  });
}

export async function confirmLevels(
  ticker: string,
  enrichmentId: string,
  confirmedIndices: number[]
): Promise<LevelConfirmResult> {
  return request<LevelConfirmResult>(`/analysis/${ticker}/enrich/confirm`, {
    method: "POST",
    body: JSON.stringify({ enrichment_id: enrichmentId, confirmed_indices: confirmedIndices }),
  });
}
