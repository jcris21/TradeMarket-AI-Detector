"use client";

import React, { useCallback, useState } from "react";
import { useAnalysis } from "@/lib/use-analysis";
import { usePerformance } from "@/lib/use-performance";
import type { AssetAnalysis, RunStatus } from "@/lib/types";
import BetSizeCell from "@/components/BetSizeCell";
import FreshnessBadge from "@/components/FreshnessBadge";
import PerformanceSummaryPanel from "@/components/PerformanceSummaryPanel";

interface OpportunitiesPanelProps {
  onTickerSelect: (ticker: string) => void;
  onInjectChat: (message: string) => void;
}

type TabId = "active" | "archive";

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

/** Stage pill (DATA / SCORING) shown during an active run. */
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

/** Live progress bar + ETA + error badge for an active run (US-204). */
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

/** Score breakdown bar showing quant components + enrichment glow (10.1 / 10.2). */
function ScoreBreakdownBar({ asset }: { asset: AssetAnalysis }) {
  const sq = asset.score_quant ?? asset.score ?? 0;
  const hasEnrichment = asset.enrichment_delta != null && asset.enrichment_delta !== 0;
  const displayScore = asset.score_enriched ?? asset.score_quant ?? asset.score;
  const enrichedLabel = asset.score_enriched != null ? "enriched" : "quant";

  // Approximate component widths based on max possible per component
  const summary = asset.indicators_summary as Record<string, unknown>;
  const rr = asset.risk_reward_ratio ?? 0;
  const rrPct = Math.min((rr >= 4 ? 30 : rr >= 3 ? 22 : rr >= 2 ? 14 : 0) / 100, 1) * 30;
  const confluencePct = 20;
  const trendPct = 10;
  const restPct = Math.max(0, sq - rrPct - confluencePct - trendPct);

  return (
    <div className="px-3 py-1.5 bg-bg-hover border-b border-border">
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
    </div>
  );
}

function SignalTable({
  signals,
  onRowClick,
}: {
  signals: AssetAnalysis[];
  onRowClick: (asset: AssetAnalysis) => void;
}) {
  const [expandedTicker, setExpandedTicker] = useState<string | null>(null);

  if (signals.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-text-muted text-sm py-8">
        Sin señales en este rango
      </div>
    );
  }
  return (
    <table className="w-full text-xs">
      <thead className="sticky top-0 bg-bg-panel border-b border-border">
        <tr className="text-text-muted text-left h-8">
          <th className="px-3 py-0 w-8 text-label-caps">#</th>
          <th className="px-3 py-0 text-label-caps">Ticker</th>
          <th className="px-3 py-0 text-label-caps">Score</th>
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
      <tbody>
        {signals.map((asset) => {
          const scoreDimmed =
            asset.freshness_status === "aged" || asset.freshness_status === "expired";
          const displayScore = asset.score_enriched ?? asset.score_quant ?? asset.score;
          const hasEnrichment = asset.enrichment_delta != null && asset.enrichment_delta !== 0;
          const scoreLabel = asset.score_enriched != null ? "E" : asset.score_quant != null ? "Q" : "";
          const isExpanded = expandedTicker === asset.ticker;
          return (
            <React.Fragment key={asset.ticker}>
            <tr
              onClick={() => {
                setExpandedTicker(isExpanded ? null : asset.ticker);
                onRowClick(asset);
              }}
              className="h-8 border-b border-border hover:bg-bg-hover cursor-pointer transition-colors"
            >
              <td className="px-3 py-0 text-text-muted font-mono">{asset.rank}</td>
              <td className="px-3 py-0 font-mono font-bold text-accent-blue">{asset.ticker}</td>
              <td className={`px-3 py-0 font-mono${scoreDimmed ? " opacity-40" : ""}`}>
                <span
                  className={hasEnrichment ? "text-amber-400" : ""}
                  style={hasEnrichment ? { textShadow: "0 0 6px rgba(251,191,36,0.5)" } : undefined}
                >
                  {displayScore?.toFixed(0) ?? "—"}
                </span>
                {scoreLabel && (
                  <span className="ml-0.5 text-label-caps text-text-muted">{scoreLabel}</span>
                )}
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
                </div>
              </td>
              <td className="px-3 py-0">
                {asset.freshness_status != null && asset.freshness_age_hours != null ? (
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
                <td colSpan={11} className="p-0">
                  <ScoreBreakdownBar asset={asset} />
                </td>
              </tr>
            )}
            </React.Fragment>
          );
        })}
      </tbody>
    </table>
  );
}

export default function OpportunitiesPanel({
  onTickerSelect,
  onInjectChat,
}: OpportunitiesPanelProps) {
  const {
    top5,
    results,
    status,
    runStatus,
    previewResults,
    lastAnalyzedAt,
    errorMessage,
    triggerRun,
    loadPreview,
    addTicker,
    getArgument,
  } = useAnalysis();
  const { performance, isLoading: perfLoading } = usePerformance(status);
  const [newTicker, setNewTicker] = useState("");
  const [addError, setAddError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabId>("active");
  const [showPreview, setShowPreview] = useState(false);

  const isRunning = status === "running";
  const isFailed =
    status === "error" && runStatus?.stage === "failed" && runStatus.errors_so_far.length > 0;
  const canPreview = (runStatus?.tickers_completed ?? 0) >= 20;

  const handlePreview = useCallback(async () => {
    await loadPreview();
    setShowPreview(true);
  }, [loadPreview]);

  const activeSignals = results.filter((a) => a.freshness_status !== "expired");
  const archivedSignals = results.filter((a) => a.freshness_status === "expired");

  // Fall back to top5 (pre-filtered by R/R) when freshness data is absent
  const displayedSignals =
    activeTab === "active"
      ? activeSignals.length > 0
        ? activeSignals
        : top5
      : archivedSignals;

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

  return (
    <div className="flex flex-col h-full border-t border-border bg-bg-panel">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-border shrink-0">
        <div className="flex items-center gap-3">
          <span className="text-label-caps text-accent-yellow">TOP OPORTUNIDADES</span>
          {minutesAgo !== null && (
            <span className="text-xs text-text-muted">
              actualizado hace {minutesAgo} min
            </span>
          )}
          <ProgressLabel status={status} />
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={triggerRun}
            disabled={status === "running"}
            className="px-3 py-1 text-label-caps bg-accent-blue text-bg-primary rounded hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {status === "running" ? "Analizando..." : "Analizar"}
          </button>
        </div>
      </div>

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

      {/* Live run progress */}
      {isRunning && runStatus && (
        <RunProgress
          runStatus={runStatus}
          onPreview={handlePreview}
          showPreviewButton={canPreview}
        />
      )}

      {/* Failed-run banner (7.10) */}
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

      {/* Partial preview (7.8) */}
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
          <SignalTable signals={previewResults} onRowClick={handleRowClick} />
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
          <SignalTable signals={displayedSignals} onRowClick={handleRowClick} />
        )}
      </div>

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
  );
}
