"use client";

import { useCallback, useState } from "react";
import { useAnalysis } from "@/lib/use-analysis";
import type { AssetAnalysis } from "@/lib/types";

interface OpportunitiesPanelProps {
  onTickerSelect: (ticker: string) => void;
  onInjectChat: (message: string) => void;
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

export default function OpportunitiesPanel({
  onTickerSelect,
  onInjectChat,
}: OpportunitiesPanelProps) {
  const { top5, results, status, lastAnalyzedAt, errorMessage, triggerRun, addTicker, getArgument } =
    useAnalysis();
  const [newTicker, setNewTicker] = useState("");
  const [addError, setAddError] = useState<string | null>(null);

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

  return (
    <div className="flex flex-col h-full border-t border-border bg-bg-panel">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-border shrink-0">
        <div className="flex items-center gap-3">
          <span className="text-sm font-semibold text-accent-yellow">TOP OPORTUNIDADES</span>
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
            className="px-3 py-1 text-xs bg-purple-secondary text-white rounded hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed font-mono"
          >
            {status === "running" ? "Analizando..." : "🔍 Analizar"}
          </button>
        </div>
      </div>

      {/* Error state */}
      {errorMessage && (
        <div className="mx-4 mt-2 px-3 py-2 bg-red-900/40 border border-red-700 rounded text-xs text-red-300">
          {errorMessage}
        </div>
      )}

      {/* Table */}
      <div className="flex-1 overflow-auto min-h-0">
        {top5.length === 0 && status !== "running" ? (
          <div className="flex items-center justify-center h-full text-text-muted text-sm">
            {status === "idle"
              ? 'Presiona "Analizar" para obtener oportunidades'
              : "Sin oportunidades con ratio ≥ 3:1"}
          </div>
        ) : (
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-bg-panel border-b border-border">
              <tr className="text-text-muted text-left">
                <th className="px-3 py-2 w-8">#</th>
                <th className="px-3 py-2">Ticker</th>
                <th className="px-3 py-2">Score</th>
                <th className="px-3 py-2">R/R</th>
                <th className="px-3 py-2">Entry</th>
                <th className="px-3 py-2">Target</th>
                <th className="px-3 py-2">Stop</th>
                <th className="px-3 py-2">Señal</th>
              </tr>
            </thead>
            <tbody>
              {top5.map((asset) => (
                <tr
                  key={asset.ticker}
                  onClick={() => handleRowClick(asset)}
                  className="border-b border-border hover:bg-bg-hover cursor-pointer transition-colors"
                >
                  <td className="px-3 py-2 text-text-muted font-mono">{asset.rank}</td>
                  <td className="px-3 py-2 font-mono font-bold text-blue-primary">{asset.ticker}</td>
                  <td className="px-3 py-2 font-mono">{asset.score?.toFixed(0) ?? "—"}</td>
                  <td className="px-3 py-2 font-mono text-accent-yellow">
                    {asset.risk_reward_ratio.toFixed(1)}x
                  </td>
                  <td className="px-3 py-2 font-mono">${asset.entry_price.toFixed(2)}</td>
                  <td className="px-3 py-2 font-mono text-green-400">${asset.target_price.toFixed(2)}</td>
                  <td className="px-3 py-2 font-mono text-red-400">${asset.stop_loss.toFixed(2)}</td>
                  <td className="px-3 py-2">
                    <SignalBadge signal={asset.signal} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
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
