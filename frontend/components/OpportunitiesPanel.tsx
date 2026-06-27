"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { useAnalysis } from "@/lib/use-analysis";
import { usePerformance } from "@/lib/use-performance";
import type { AssetAnalysis, RunStatus } from "@/lib/types";
import BetSizeCell from "@/components/BetSizeCell";
import FreshnessBadge from "@/components/FreshnessBadge";
import PerformanceSummaryPanel from "@/components/PerformanceSummaryPanel";
import TraderChartUpload from "@/components/TraderChartUpload";

interface OpportunitiesPanelProps {
  onTickerSelect: (ticker: string) => void;
  onInjectChat: (message: string) => void;
  isExpanded?: boolean;
  onExpandToggle?: () => void;
}

type TabId = "active" | "archive";

// ── Score Band (US-403) ───────────────────────────────────────────────────────

export type ScoreBand = "ELITE" | "STRONG" | "QUALIFYING" | "NONE";

export function getScoreBand(score: number | null | undefined): ScoreBand {
  if (score == null) return "NONE";
  if (score >= 75) return "ELITE";
  if (score >= 60) return "STRONG";
  if (score >= 50) return "QUALIFYING";
  return "NONE";
}

export const BAND_COLORS: Record<ScoreBand, string> = {
  ELITE: "#ECAD0A",
  STRONG: "#209DD7",
  QUALIFYING: "#888888",
  NONE: "#444444",
};

function ScoreBandBadge({ band }: { band: ScoreBand }) {
  if (band === "NONE") return null;
  const color = BAND_COLORS[band];
  return (
    <span
      className="px-1 py-0.5 rounded text-xs font-mono font-bold"
      style={{ border: `1px solid ${color}`, color }}
    >
      {band}
    </span>
  );
}

function ExpiredBadge() {
  return (
    <span
      className="px-1 py-0.5 rounded text-xs font-mono font-bold"
      style={{ border: "1px solid #6B7280", color: "#6B7280" }}
    >
      EXPIRED
    </span>
  );
}

function MiniScoreBar({
  score_quant,
  band,
  enrichment_delta,
}: {
  score_quant: number;
  band: ScoreBand;
  enrichment_delta?: number | null;
}) {
  const color = BAND_COLORS[band];
  const basePx = (score_quant / 100) * 64;
  const delta = enrichment_delta ?? 0;
  const remainPx = 64 - basePx;
  const deltaPx = delta !== 0 ? Math.min(remainPx, (Math.abs(delta) / 100) * 64) : 0;
  const deltaColor = delta > 0 ? "#22c55e" : "#ef4444";

  return (
    <div className="flex items-center gap-1.5">
      <span className="text-xs font-mono tabular-nums" style={{ color, minWidth: 24 }}>
        {Math.round(score_quant)}
      </span>
      <div className="relative rounded overflow-hidden" style={{ width: 64, height: 6, background: "#2a2a2a" }}>
        <div style={{ position: "absolute", left: 0, top: 0, width: basePx, height: 6, background: color }} />
        {deltaPx > 0 && (
          <div
            style={{
              position: "absolute",
              left: basePx,
              top: 0,
              width: deltaPx,
              height: 6,
              background: deltaColor,
            }}
          />
        )}
      </div>
    </div>
  );
}

// ── Freshness Row (US-404) ────────────────────────────────────────────────────

const FRESHNESS_DOT_COLOR: Record<string, string> = {
  fresh: "#22c55e",
  active: "#F59E0B",
  aged: "#ef4444",
  stale: "#ef4444",
  expired: "#6B7280",
};

export function formatAge(analyzedAt: string, nowMs: number): string {
  const diffMs = nowMs - new Date(analyzedAt).getTime();
  const totalMin = Math.floor(diffMs / 60_000);
  if (totalMin < 60) return `${totalMin}m ago`;
  const h = Math.floor(totalMin / 60);
  const m = totalMin % 60;
  return m === 0 ? `${h}h ago` : `${h}h ${m}m ago`;
}

function FreshnessDot({ status }: { status: string }) {
  const color = FRESHNESS_DOT_COLOR[status] ?? "#6B7280";
  return (
    <span
      style={{
        display: "inline-block",
        width: 8,
        height: 8,
        borderRadius: "50%",
        background: color,
        flexShrink: 0,
      }}
    />
  );
}

function ScoreQuantDelta({ current, prior }: { current: number | null | undefined; prior: number | null | undefined }) {
  if (prior == null || current == null) return null;
  const delta = current - prior;
  const abs = Math.round(Math.abs(delta));
  if (Math.abs(delta) <= 3) {
    return <span className="text-xs font-mono" style={{ color: "#6B7280" }}>=</span>;
  }
  if (delta > 3) {
    return <span className="text-xs font-mono" style={{ color: "#22c55e" }}>▲ +{abs}</span>;
  }
  return <span className="text-xs font-mono" style={{ color: "#ef4444" }}>▼ -{abs}</span>;
}

function EnrichmentBadge({ delta }: { delta?: number | null }) {
  if (delta == null || delta === 0) return null;
  const positive = delta > 0;
  const color = positive ? "#22c55e" : "#ef4444";
  const label = positive ? `+${Math.round(delta)} visual` : `${Math.round(delta)} visual`;
  return (
    <span
      className="text-xs font-mono px-1 py-0.5 rounded"
      style={{ border: `1px solid ${color}`, color }}
    >
      {label}
    </span>
  );
}

// ── Pagination (US-401) ───────────────────────────────────────────────────────

const PAGE_SIZE = 10;

// ── Orphaned / Stale badges ───────────────────────────────────────────────────

const ORPHANED_DAYS = 35;

function isOrphaned(asset: AssetAnalysis): boolean {
  if (asset.outcome !== null && asset.outcome !== undefined) return false;
  if (!asset.analyzed_at) return false;
  const ageMs = Date.now() - new Date(asset.analyzed_at).getTime();
  return ageMs > ORPHANED_DAYS * 24 * 60 * 60 * 1000;
}

function OrphanedBadge() {
  return (
    <span
      className="px-2 py-0.5 rounded text-xs font-mono font-bold bg-amber-900 text-amber-300 border border-amber-700"
      title="No outcome detected after 35 trading days — review manually"
    >
      ⚠ Orphaned
    </span>
  );
}

function StaleBadge() {
  return (
    <span
      className="px-2 py-0.5 rounded text-xs font-mono font-bold border"
      style={{ color: "#ecad0a", borderColor: "#ecad0a" }}
      title="Datos del análisis anterior — yfinance no disponible al momento del run"
    >
      Stale data
    </span>
  );
}

function SignalBadge({ signal }: { signal: string }) {
  const colors: Record<string, string> = {
    BUY: "bg-green-900 text-green-300 border border-green-700",
    WAIT: "bg-yellow-900 text-yellow-300 border border-yellow-700",
    AVOID: "bg-red-900 text-red-300 border border-red-700",
  };
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-mono font-bold ${colors[signal] ?? ""}`}>
      {signal}
    </span>
  );
}

function ProgressLabel({ status }: { status: string }) {
  const labels: Record<string, string> = {
    idle: "",
    running: "Analizando...",
    done: "",
    error: "",
  };
  return labels[status] ? (
    <span className="text-xs text-text-muted animate-pulse">{labels[status]}</span>
  ) : null;
}

function StageBadge({ stage }: { stage: RunStatus["stage"] }) {
  if (stage !== "data" && stage !== "scoring") return null;
  const label = stage === "data" ? "DATA" : "SCORING";
  const cls =
    stage === "data"
      ? "bg-blue-900 text-blue-300 border-blue-700"
      : "bg-purple-900 text-purple-300 border-purple-700";
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-mono font-bold border ${cls}`}>
      {label}
    </span>
  );
}

function RunProgress({
  runStatus,
  onPreview,
  showPreviewButton,
}: {
  runStatus: RunStatus;
  onPreview: () => void;
  showPreviewButton: boolean;
}) {
  const { stage, tickers_completed, tickers_total, estimated_remaining_seconds, errors_so_far } =
    runStatus;
  if (stage === "complete" || stage === "failed") return null;
  const pct =
    tickers_total > 0 ? Math.min(100, Math.round((tickers_completed / tickers_total) * 100)) : 0;
  return (
    <div className="px-4 py-2 border-b border-border space-y-1.5" data-testid="run-progress">
      <div className="flex items-center gap-2">
        <StageBadge stage={stage} />
        <span className="text-xs font-mono text-text-muted tabular-nums">
          {tickers_completed}/{tickers_total}
        </span>
        {estimated_remaining_seconds !== null && (
          <span className="text-xs font-mono text-text-muted" data-testid="run-eta">
            ~{Math.round(estimated_remaining_seconds)}s remaining
          </span>
        )}
        {errors_so_far.length > 0 && (
          <span
            className="px-1.5 py-0.5 rounded text-xs font-mono font-bold bg-red-900 text-red-300 border border-red-700"
            title={errors_so_far.map((e) => `${e.ticker}: ${e.error_message}`).join("\n")}
            data-testid="run-error-badge"
          >
            {errors_so_far.length} err
          </span>
        )}
        {showPreviewButton && (
          <button
            onClick={onPreview}
            className="ml-auto px-2 py-0.5 text-xs font-mono bg-bg-hover border border-border rounded hover:border-accent-yellow"
          >
            Preview Top 20
          </button>
        )}
      </div>
      <div className="h-1.5 w-full bg-bg-hover rounded overflow-hidden">
        <div
          className="h-full bg-accent-blue transition-all duration-500"
          style={{ width: `${pct}%` }}
          data-testid="progress-bar-fill"
        />
      </div>
    </div>
  );
}

function Spinner() {
  return (
    <svg className="animate-spin h-3 w-3 inline-block" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
    </svg>
  );
}

function ScoreBreakdownBar({ asset }: { asset: AssetAnalysis }) {
  const sq = asset.score_quant ?? asset.score ?? 0;
  const hasEnrichment = asset.enrichment_delta != null && asset.enrichment_delta !== 0;
  const isAutoScreenshot =
    asset.enrichment_type === "auto_screenshot" &&
    asset.enrichment_delta != null &&
    asset.score_quant != null;
  const displayScore = asset.score_enriched ?? asset.score_quant ?? asset.score;
  const enrichedLabel = asset.score_enriched != null ? "enriched" : "quant";

  const rr = asset.risk_reward_ratio ?? 0;
  const rrPct = Math.min((rr >= 4 ? 30 : rr >= 3 ? 22 : rr >= 2 ? 14 : 0) / 100, 1) * 30;
  const confluencePct = 20;
  const trendPct = 10;
  const restPct = Math.max(0, sq - rrPct - confluencePct - trendPct);

  return (
    <div className="px-3 py-1.5 bg-bg-hover border-b border-border">
      {isAutoScreenshot ? (
        <div className="flex items-center gap-3 mb-1">
          <span className="text-xs text-text-muted font-mono">Quant</span>
          <span className="text-xs font-mono font-bold tabular-nums text-white">
            {asset.score_quant?.toFixed(1) ?? "—"}
          </span>
          <span className="text-xs text-text-muted font-mono">→</span>
          <span
            className="text-xs font-mono font-bold tabular-nums text-amber-400"
            style={{ textShadow: "0 0 8px rgba(251,191,36,0.6)" }}
          >
            {asset.score_enriched?.toFixed(1) ?? "—"}
          </span>
          <span className="text-xs font-mono text-amber-400">
            +{asset.enrichment_delta?.toFixed(1)} visual, auto screenshot
          </span>
        </div>
      ) : (
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs text-text-muted font-mono">Score</span>
          <span
            className={`text-xs font-mono font-bold tabular-nums${hasEnrichment ? " text-amber-400" : " text-white"}`}
            style={hasEnrichment ? { textShadow: "0 0 8px rgba(251,191,36,0.6)" } : undefined}
          >
            {displayScore?.toFixed(1) ?? "—"}
          </span>
          <span className="text-xs text-text-muted font-mono">({enrichedLabel})</span>
          {hasEnrichment && (
            <span className="text-xs font-mono text-amber-400">
              Δ{(asset.enrichment_delta ?? 0) > 0 ? "+" : ""}
              {asset.enrichment_delta?.toFixed(1)}
            </span>
          )}
        </div>
      )}
      <div className="flex h-1.5 rounded overflow-hidden gap-px w-full max-w-xs">
        <div
          className="bg-accent-blue opacity-90"
          style={{ width: `${(rrPct / 100) * 100}%` }}
          title={`R/R: ${rrPct.toFixed(0)}pts`}
        />
        <div
          className="bg-accent-yellow opacity-70"
          style={{ width: `${(confluencePct / 100) * 100}%` }}
          title="Confluence: up to 20pts"
        />
        <div
          className="bg-purple-400 opacity-70"
          style={{ width: `${(trendPct / 100) * 100}%` }}
          title="Trend/BB/ATR/Support: up to 34pts"
        />
        <div
          className="bg-gray-500 opacity-50"
          style={{ width: `${(restPct / 100) * 100}%` }}
          title="Adjustments"
        />
        {hasEnrichment && (
          <div
            className="bg-amber-400 opacity-80"
            style={{ width: `${(Math.abs(asset.enrichment_delta ?? 0) / 100) * 100}%` }}
            title={`Enrichment: ${asset.enrichment_delta?.toFixed(1)}pts`}
          />
        )}
      </div>
      <div className="flex gap-3 mt-1 text-label-caps opacity-60">
        <span style={{ color: "#209dd7" }}>R/R</span>
        <span style={{ color: "#ecad0a" }}>Conf</span>
        <span style={{ color: "#a78bfa" }}>Trend</span>
        <span className="text-gray-400">Adj</span>
        {hasEnrichment && <span style={{ color: "#fbbf24" }}>Enrich</span>}
      </div>
      {asset.enrichment_status === "pending" && !asset.enrichment_delta && (
        <div className="flex items-center gap-1.5 mt-1">
          <Spinner />
          <span className="text-xs font-mono text-amber-400">Enrichment in progress…</span>
        </div>
      )}
      {asset.argument && (
        <p className="mt-2 text-xs text-text-muted font-mono leading-relaxed">{asset.argument}</p>
      )}
    </div>
  );
}

// ── SignalTable with band dividers, freshness dots, and score deltas ──────────

function SignalTable({
  signals,
  onRowClick,
  onTickerConfirmed,
  nowMs,
  isArchive,
}: {
  signals: AssetAnalysis[];
  onRowClick: (asset: AssetAnalysis) => void;
  onTickerConfirmed: (ticker: string) => Promise<void>;
  nowMs: number;
  isArchive: boolean;
}) {
  const [expandedTicker, setExpandedTicker] = useState<string | null>(null);

  if (signals.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-text-muted text-sm py-8">
        Sin señales en este rango
      </div>
    );
  }

  const rows: React.ReactNode[] = [];
  let prevBand: ScoreBand | null = null;

  for (const asset of signals) {
    const band = getScoreBand(asset.score_quant ?? asset.score);
    const isExpanded = expandedTicker === asset.ticker;
    const isExpiredRow = isArchive && asset.freshness_status === "expired";

    // Band divider (4.5)
    if (prevBand !== null && band !== prevBand && !isArchive) {
      const divColor = BAND_COLORS[band];
      rows.push(
        <tr key={`divider-${band}-${asset.ticker}`}>
          <td colSpan={12} className="px-3 py-1">
            <div className="flex items-center gap-2">
              <div className="flex-1 h-px" style={{ background: divColor, opacity: 0.4 }} />
              <span className="text-xs font-mono" style={{ color: divColor }}>
                {band}
              </span>
              <div className="flex-1 h-px" style={{ background: divColor, opacity: 0.4 }} />
            </div>
          </td>
        </tr>
      );
    }
    prevBand = band;

    const scoreDimmed =
      asset.freshness_status === "aged" || asset.freshness_status === "expired";
    const displayScore = asset.score_enriched ?? asset.score_quant ?? asset.score;
    const hasEnrichment = asset.enrichment_delta != null && asset.enrichment_delta !== 0;
    const scoreLabel = asset.score_enriched != null ? "E" : asset.score_quant != null ? "Q" : "";

    rows.push(
      <React.Fragment key={asset.ticker}>
        <tr
          onClick={() => {
            setExpandedTicker(isExpanded ? null : asset.ticker);
            onRowClick(asset);
          }}
          className="h-8 border-b border-border hover:bg-bg-hover cursor-pointer transition-colors"
          style={isExpiredRow ? { opacity: 0.4 } : undefined}
        >
          <td className="px-3 py-0 text-text-muted font-mono">{asset.rank}</td>
          <td
            className="px-3 py-0 font-mono font-bold text-accent-blue"
            style={isExpiredRow ? { textDecoration: "line-through" } : undefined}
          >
            {asset.ticker}
          </td>
          {/* Score band badge */}
          <td className="px-2 py-0">
            {isExpiredRow ? <ExpiredBadge /> : <ScoreBandBadge band={band} />}
          </td>
          {/* MiniScoreBar (US-403) */}
          <td className="px-2 py-0">
            {asset.score_quant != null ? (
              <MiniScoreBar
                score_quant={asset.score_quant}
                band={band}
                enrichment_delta={asset.enrichment_delta}
              />
            ) : (
              <span className={`px-3 py-0 font-mono${scoreDimmed ? " opacity-40" : ""}`}>
                <span
                  className={hasEnrichment ? "text-amber-400" : ""}
                  style={hasEnrichment ? { textShadow: "0 0 6px rgba(251,191,36,0.5)" } : undefined}
                >
                  {displayScore?.toFixed(0) ?? "—"}
                </span>
                {scoreLabel && (
                  <span className="ml-0.5 text-label-caps text-text-muted">{scoreLabel}</span>
                )}
              </span>
            )}
          </td>
          {/* ScoreQuantDelta (US-404 P1) */}
          <td className="px-2 py-0">
            <ScoreQuantDelta current={asset.score_quant} prior={asset.prior_score_quant} />
          </td>
          <td className="px-3 py-0 font-mono text-accent-yellow">
            {asset.risk_reward_ratio.toFixed(1)}x
          </td>
          <td className="px-3 py-0 font-mono tabular-nums">${asset.entry_price.toFixed(2)}</td>
          <td className="px-3 py-0 font-mono tabular-nums text-gain">${asset.target_price.toFixed(2)}</td>
          <td className="px-3 py-0 font-mono tabular-nums text-loss">${asset.stop_loss.toFixed(2)}</td>
          <td className="px-3 py-0">
            <div className="flex items-center gap-1">
              <SignalBadge signal={asset.signal} />
              {isOrphaned(asset) && <OrphanedBadge />}
              {asset.is_stale && <StaleBadge />}
              <EnrichmentBadge delta={asset.enrichment_delta} />
            </div>
          </td>
          {/* Freshness dot + age (US-404) */}
          <td className="px-3 py-0">
            {asset.freshness_status != null && asset.analyzed_at ? (
              <div className="flex items-center gap-1.5">
                <FreshnessDot status={asset.freshness_status} />
                <span className="text-xs font-mono text-text-muted">
                  {formatAge(asset.analyzed_at, nowMs)}
                </span>
              </div>
            ) : asset.freshness_status != null && asset.freshness_age_hours != null ? (
              <FreshnessBadge
                status={asset.freshness_status}
                ageHours={asset.freshness_age_hours}
              />
            ) : (
              <span className="text-text-muted">—</span>
            )}
          </td>
          <td className="px-3 py-0 font-mono">
            {asset.atr_14_pct == null ? (
              <span className="text-text-muted">—</span>
            ) : asset.stop_viable === true ? (
              <span className="text-gain">✔ ATR</span>
            ) : asset.stop_viable === false ? (
              <span className="text-loss">❌ ATR</span>
            ) : (
              <span className="text-text-muted">—</span>
            )}
          </td>
          <td className="px-3 py-0">
            {asset.signal === "BUY" ? (
              <BetSizeCell
                gain={asset.expected_gain_per10 ?? null}
                loss={asset.expected_loss_per10 ?? null}
                ev={asset.expected_value_per10 ?? null}
                hrUsed={asset.hit_rate_used ?? null}
                hrSrc={asset.hit_rate_source ?? null}
              />
            ) : (
              <span className="text-text-muted">—</span>
            )}
          </td>
        </tr>
        {isExpanded && (
          <tr key={`${asset.ticker}-breakdown`} className="border-b border-border">
            <td colSpan={13} className="p-0">
              <ScoreBreakdownBar asset={asset} />
              <div className="px-3 pb-2">
                <TraderChartUpload
                  ticker={asset.ticker}
                  onConfirmed={() => void onTickerConfirmed(asset.ticker)}
                />
              </div>
            </td>
          </tr>
        )}
      </React.Fragment>
    );
  }

  return (
    <table className="w-full text-xs">
      <thead className="sticky top-0 bg-bg-panel border-b border-border">
        <tr className="text-text-muted text-left h-8">
          <th className="px-3 py-0 w-8 text-label-caps">#</th>
          <th className="px-3 py-0 text-label-caps">Ticker</th>
          <th className="px-2 py-0 text-label-caps">Band</th>
          <th className="px-2 py-0 text-label-caps">Score</th>
          <th className="px-2 py-0 text-label-caps">Δ</th>
          <th className="px-3 py-0 text-label-caps">R/R</th>
          <th className="px-3 py-0 text-label-caps">Entry</th>
          <th className="px-3 py-0 text-label-caps">Target</th>
          <th className="px-3 py-0 text-label-caps">Stop</th>
          <th className="px-3 py-0 text-label-caps">Señal</th>
          <th className="px-3 py-0 text-label-caps">Freshness</th>
          <th className="px-3 py-0 text-label-caps">ATR</th>
          <th className="px-3 py-0 text-label-caps">Bet Size</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

function ExpandIcon({ expanded }: { expanded: boolean }) {
  return expanded ? (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M9 2H12V5M5 12H2V9M12 9V12H9M2 5V2H5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ) : (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M2 9V12H5M12 5V2H9M5 2H2V5M9 12H12V9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

export default function OpportunitiesPanel({
  onTickerSelect,
  onInjectChat,
  isExpanded = false,
  onExpandToggle,
}: OpportunitiesPanelProps) {
  const {
    top5,
    results,
    totalAnalyzed,
    status,
    runStatus,
    previewResults,
    lastAnalyzedAt,
    errorMessage,
    regimeGateActive,
    vixValue,
    triggerRun,
    loadPreview,
    addTicker,
    getArgument,
    refreshTicker,
  } = useAnalysis();
  const { performance, isLoading: perfLoading } = usePerformance(status);
  const [newTicker, setNewTicker] = useState("");
  const [addError, setAddError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabId>("active");
  const [showPreview, setShowPreview] = useState(false);

  // ── Pagination state (US-401) ─────────────────────────────────────────────
  const [currentPage, setCurrentPage] = useState(1);

  // ── Collapse state (US-402) ───────────────────────────────────────────────
  const [collapsed, setCollapsed] = useState(false);
  const [completionBanner, setCompletionBanner] = useState<string | null>(null);
  const collapsedAtRunStartRef = useRef(collapsed);

  // Restore persisted preference after mount (avoids SSR/client hydration mismatch)
  useEffect(() => {
    if (localStorage.getItem("finally_top_opps_collapsed") === "true") {
      setCollapsed(true);
    }
  }, []);

  const toggleCollapsed = useCallback(() => {
    setCollapsed((prev) => {
      const next = !prev;
      localStorage.setItem("finally_top_opps_collapsed", String(next));
      return next;
    });
  }, []);

  // Shift+O global shortcut (US-402 P1)
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.shiftKey && e.key === "O") toggleCollapsed();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [toggleCollapsed]);

  // ── Freshness tick (US-404) ───────────────────────────────────────────────
  const [nowMs, setNowMs] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNowMs(Date.now()), 60_000);
    return () => clearInterval(id);
  }, []);

  // ── Derived signal lists ──────────────────────────────────────────────────
  const isRunning = status === "running";
  const isFailed =
    status === "error" && runStatus?.stage === "failed" && runStatus.errors_so_far.length > 0;
  const canPreview = (runStatus?.tickers_completed ?? 0) >= 20;

  const activeSignals = results.filter((a) => a.freshness_status !== "expired");
  const archivedSignals = results.filter((a) => a.freshness_status === "expired");
  const displayedSignals =
    activeTab === "active"
      ? activeSignals.length > 0
        ? activeSignals
        : top5
      : archivedSignals;

  // Band counts for summary line (US-403 P1)
  const bandCounts = displayedSignals.reduce<Record<ScoreBand, number>>(
    (acc, a) => {
      const b = getScoreBand(a.score_quant ?? a.score);
      acc[b] = (acc[b] ?? 0) + 1;
      return acc;
    },
    { ELITE: 0, STRONG: 0, QUALIFYING: 0, NONE: 0 }
  );

  // Pagination (US-401)
  const totalPages = Math.ceil(displayedSignals.length / PAGE_SIZE);
  const pageSignals = displayedSignals.slice(
    (currentPage - 1) * PAGE_SIZE,
    currentPage * PAGE_SIZE
  );

  // Reset page on new run (US-401)
  useEffect(() => {
    setCurrentPage(1);
  }, [lastAnalyzedAt]);

  // Capture collapsed state at run start; auto-expand on completion (US-402)
  const prevStatus = useRef(status);
  useEffect(() => {
    if (prevStatus.current !== "running" && status === "running") {
      collapsedAtRunStartRef.current = collapsed;
    }
    if (prevStatus.current === "running" && status === "done") {
      if (!collapsedAtRunStartRef.current) {
        setCollapsed(false);
        if (typeof window !== "undefined") {
          localStorage.setItem("finally_top_opps_collapsed", "false");
        }
        const count = displayedSignals.length;
        setCompletionBanner(`Analysis complete — ${count} new signals available`);
        setTimeout(() => setCompletionBanner(null), 5000);
      }
    }
    prevStatus.current = status;
  }, [status, collapsed, displayedSignals.length]);

  const handlePreview = useCallback(async () => {
    await loadPreview();
    setShowPreview(true);
  }, [loadPreview]);

  const handleRowClick = useCallback(
    async (asset: AssetAnalysis) => {
      onTickerSelect(asset.ticker);
      const arg = await getArgument(asset.ticker);
      if (arg) {
        onInjectChat(`Muéstrame el análisis técnico de ${asset.ticker}: ${arg}`);
      } else {
        onInjectChat(`Muéstrame el análisis técnico de ${asset.ticker}`);
      }
    },
    [onTickerSelect, onInjectChat, getArgument]
  );

  const handleAddTicker = useCallback(async () => {
    const t = newTicker.trim().toUpperCase();
    if (!t) return;
    setAddError(null);
    try {
      await addTicker(t);
      setNewTicker("");
    } catch {
      setAddError(`No se pudo agregar ${t}`);
    }
  }, [newTicker, addTicker]);

  // Keyboard page nav (US-401)
  const handlePanelKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLDivElement>) => {
      if (e.key === "ArrowRight" && currentPage < totalPages) {
        setCurrentPage((p) => p + 1);
      } else if (e.key === "ArrowLeft" && currentPage > 1) {
        setCurrentPage((p) => p - 1);
      }
    },
    [currentPage, totalPages]
  );

  const minutesAgo =
    lastAnalyzedAt
      ? Math.round((Date.now() - new Date(lastAnalyzedAt).getTime()) / 60_000)
      : null;

  const tabClass = (tab: TabId) =>
    `px-3 py-1.5 text-xs font-mono transition-colors ${
      activeTab === tab
        ? "border-b-2 border-accent-yellow text-accent-yellow"
        : "text-text-muted hover:text-white border-b-2 border-transparent"
    }`;

  // Summary line content (US-401 + US-403 P1)
  const showingCount = Math.min(PAGE_SIZE, displayedSignals.length - (currentPage - 1) * PAGE_SIZE);
  const totalCount = displayedSignals.length;
  const bandSummaryParts = (["ELITE", "STRONG", "QUALIFYING"] as ScoreBand[])
    .filter((b) => bandCounts[b] > 0)
    .map((b) => `${b}: ${bandCounts[b]}`);

  return (
    <div
      className="flex flex-col h-full border-t border-border bg-bg-panel"
      tabIndex={0}
      onKeyDown={handlePanelKeyDown}
    >
      {/* Header — collapsible toggle (US-402) */}
      <div
        className="flex items-center justify-between px-4 py-2 border-b border-border shrink-0 cursor-pointer select-none"
        onClick={toggleCollapsed}
        aria-expanded={!collapsed}
      >
        <div className="flex items-center gap-3">
          <span className="text-label-caps text-accent-yellow">
            {collapsed ? "▶" : "▼"} TOP OPORTUNIDADES
          </span>
          {/* Collapsed count badge (US-402) */}
          {collapsed && displayedSignals.length > 0 && (
            <span className="text-xs font-mono text-text-muted">[{displayedSignals.length}]</span>
          )}
          {/* Regime gate badge in header (US-402 P1) */}
          {regimeGateActive && (
            <span
              className="px-1.5 py-0.5 rounded text-xs font-mono font-bold"
              style={{ color: "#C47A00", border: "1px solid #C47A00" }}
            >
              ⚠ Regime gate active
            </span>
          )}
          {!collapsed && minutesAgo !== null && (
            <span className="text-xs text-text-muted">
              actualizado hace {minutesAgo} min
            </span>
          )}
          {!collapsed && <ProgressLabel status={status} />}
          {/* Inline completion banner (US-402) */}
          {!collapsed && completionBanner && (
            <span className="text-xs font-mono text-accent-yellow animate-pulse">
              {completionBanner}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
          <button
            onClick={(e) => {
              e.stopPropagation();
              triggerRun();
            }}
            disabled={status === "running"}
            className="px-3 py-1 text-label-caps bg-accent-blue text-bg-primary rounded hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {status === "running" ? "Analizando..." : "Analizar"}
          </button>
          {onExpandToggle && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onExpandToggle();
              }}
              title={isExpanded ? "Restaurar vista" : "Expandir lista"}
              className="p-1 rounded text-text-muted hover:text-accent-yellow hover:bg-bg-hover transition-colors"
              aria-label={isExpanded ? "Restaurar vista" : "Expandir lista"}
            >
              <ExpandIcon expanded={isExpanded} />
            </button>
          )}
        </div>
      </div>

      {/* Collapsible body (US-402) */}
      <div
        className="overflow-hidden transition-all duration-200 ease-out flex flex-col"
        style={{ maxHeight: collapsed ? "0px" : "2000px" }}
      >
        {/* Tabs */}
        <div className="flex border-b border-border shrink-0 px-2">
          <button className={tabClass("active")} onClick={() => setActiveTab("active")}>
            Oportunidades
            {activeSignals.length > 0 && (
              <span className="ml-1 text-text-muted">({activeSignals.length})</span>
            )}
          </button>
          <button className={tabClass("archive")} onClick={() => setActiveTab("archive")}>
            Archivo
            {archivedSignals.length > 0 && (
              <span className="ml-1 text-text-muted">({archivedSignals.length})</span>
            )}
          </button>
        </div>

        {/* Performance summary panel */}
        {perfLoading && !performance ? (
          <div className="px-4 py-3 border-b border-border">
            <div className="h-3 bg-bg-hover rounded animate-pulse w-3/4" />
          </div>
        ) : performance ? (
          <PerformanceSummaryPanel summary={performance} />
        ) : null}

        {/* Regime gate (VIX) warning banner */}
        {regimeGateActive && (
          <div
            data-testid="regime-gate-banner"
            className="mx-4 mt-2 px-3 py-2 rounded text-xs font-mono border"
            style={{ color: "#ecad0a", borderColor: "#ecad0a", backgroundColor: "rgba(236,173,10,0.12)" }}
            role="alert"
          >
            ⚠ Régimen de mercado adverso — VIX {vixValue != null ? vixValue.toFixed(1) : "N/D"} supera el umbral. Todas las señales BUY han sido suprimidas (AVOID).
          </div>
        )}

        {/* Live run progress */}
        {isRunning && runStatus && (
          <RunProgress
            runStatus={runStatus}
            onPreview={handlePreview}
            showPreviewButton={canPreview}
          />
        )}

        {/* Failed-run banner */}
        {isFailed && (
          <div className="mx-4 mt-2 px-3 py-2 bg-red-900/40 border border-red-700 rounded text-xs text-red-300">
            <div className="font-bold mb-1">Analysis failed</div>
            <ul className="list-disc list-inside space-y-0.5">
              {runStatus!.errors_so_far.map((e, i) => (
                <li key={i}>
                  {e.ticker}: {e.error_message}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Error state */}
        {errorMessage && !isFailed && (
          <div className="mx-4 mt-2 px-3 py-2 bg-red-900/40 border border-red-700 rounded text-xs text-red-300">
            {errorMessage}
          </div>
        )}

        {/* Partial preview */}
        {showPreview && previewResults.length > 0 && (
          <div className="mx-4 mt-2 border border-accent-yellow/40 rounded overflow-hidden">
            <div className="flex items-center justify-between px-3 py-1.5 bg-bg-hover">
              <span className="text-xs font-mono text-accent-yellow">
                Preview Top 20 ({previewResults.length})
              </span>
              <button
                onClick={() => setShowPreview(false)}
                className="text-xs text-text-muted hover:text-white"
              >
                ✕
              </button>
            </div>
            <SignalTable
              signals={previewResults}
              onRowClick={handleRowClick}
              onTickerConfirmed={refreshTicker}
              nowMs={nowMs}
              isArchive={false}
            />
          </div>
        )}

        {/* Summary line (US-401) */}
        {displayedSignals.length > 0 && (
          <div className="px-4 py-1.5 text-xs font-mono text-text-muted border-b border-border shrink-0">
            Showing {showingCount} of {totalCount} qualified signals
            {totalAnalyzed > 0 ? ` (${totalAnalyzed} analyzed)` : ""}
            {bandSummaryParts.length > 0 && (
              <span className="ml-2 opacity-70">· {bandSummaryParts.join(" · ")}</span>
            )}
          </div>
        )}

        {/* Table */}
        <div className="flex-1 overflow-auto min-h-0">
          {activeTab === "active" && displayedSignals.length === 0 && status !== "running" ? (
            <div className="flex items-center justify-center h-full text-text-muted text-sm">
              {status === "idle"
                ? 'Presiona "Analizar" para obtener oportunidades'
                : "Sin oportunidades con ratio ≥ 3:1"}
            </div>
          ) : activeTab === "archive" && archivedSignals.length === 0 ? (
            <div className="flex items-center justify-center h-full text-text-muted text-sm">
              No hay señales expiradas en el archivo
            </div>
          ) : (
            <SignalTable
              signals={pageSignals}
              onRowClick={handleRowClick}
              onTickerConfirmed={refreshTicker}
              nowMs={nowMs}
              isArchive={activeTab === "archive"}
            />
          )}
        </div>

        {/* Pagination controls (US-401) */}
        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-3 px-4 py-2 border-t border-border shrink-0">
            <button
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={currentPage === 1}
              className="px-2 py-1 text-xs font-mono bg-bg-hover border border-border rounded disabled:opacity-40"
            >
              ← Prev
            </button>
            <div className="flex items-center gap-1.5">
              {Array.from({ length: totalPages }, (_, i) => (
                <span
                  key={i}
                  className="text-xs"
                  style={{ color: i + 1 === currentPage ? "#ECAD0A" : "#555" }}
                >
                  {i + 1 === currentPage ? "●" : "○"}
                </span>
              ))}
            </div>
            <span className="text-xs font-mono text-text-muted">
              Page {currentPage} of {totalPages}
            </span>
            <button
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages}
              className="px-2 py-1 text-xs font-mono bg-bg-hover border border-border rounded disabled:opacity-40"
            >
              Next →
            </button>
          </div>
        )}

        {/* Add ticker input */}
        <div className="flex items-center gap-2 px-4 py-2 border-t border-border shrink-0">
          <input
            type="text"
            value={newTicker}
            onChange={(e) => setNewTicker(e.target.value.toUpperCase())}
            onKeyDown={(e) => e.key === "Enter" && handleAddTicker()}
            placeholder="+ Agregar ticker (ej: PYPL)"
            className="flex-1 bg-bg-input border border-border rounded px-2 py-1 text-xs font-mono focus:outline-none focus:border-blue-primary"
          />
          <button
            onClick={handleAddTicker}
            className="px-2 py-1 text-xs bg-bg-hover border border-border rounded hover:border-blue-primary font-mono"
          >
            Agregar
          </button>
          {addError && <span className="text-xs text-red-400">{addError}</span>}
        </div>
      </div>
    </div>
  );
}
