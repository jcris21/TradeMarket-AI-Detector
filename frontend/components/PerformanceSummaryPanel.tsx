import type { PerformanceSummary } from "@/lib/types";

interface Props {
  summary: PerformanceSummary;
}

function statusClass(status: string | null): string {
  if (status === "green") return "text-gain";
  if (status === "red") return "text-loss";
  return "text-text-muted";
}

export default function PerformanceSummaryPanel({ summary }: Props) {
  const currentPhase = summary.phase ?? 0;

  if (summary.phase_gate_active) {
    const pct = Math.min(summary.calibration_count / 30, 1);
    return (
      <div className="px-4 py-3 border-b border-border bg-bg-panel">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-label-caps text-text-muted">
            {summary.phase_banner}
          </span>
        </div>
        <div className="w-full h-1 bg-bg-hover rounded-full overflow-hidden">
          <div
            className="h-full bg-accent-yellow rounded-full transition-all"
            style={{ width: `${Math.round(pct * 100)}%` }}
          />
        </div>
      </div>
    );
  }

  const { hit_ratio, profit_factor, realized_rr, hr_status, pf_status, rr_status } = summary;
  const resolved = summary.target_hits + summary.stop_hits;

  const hrLabel = hit_ratio != null
    ? `${summary.target_hits}/${resolved} = ${(hit_ratio * 100).toFixed(0)}%`
    : "—";

  const pfValue = profit_factor === 999.0 ? "∞" : profit_factor != null ? profit_factor.toFixed(2) : "—";
  const rrLabel = realized_rr != null ? `${realized_rr.toFixed(1)}x` : "—";

  return (
    <div className="px-4 py-2 border-b border-border bg-bg-panel">
      {/* Header row */}
      <div className="flex items-center justify-between mb-2">
        <span className="text-label-caps text-text-muted">
          {(summary.phase_banner ?? "")
            .replace(/^📊\s*/, "")
            .split("·")[0]
            .trim() || `Phase ${currentPhase}`}
        </span>
        <span className="text-label-caps text-accent-blue border border-accent-blue px-2 py-0.5 rounded">
          Live Metrics Active
        </span>
      </div>

      {/* Metrics: horizontal 3-column */}
      <div className="grid grid-cols-3 gap-4">
        <div>
          <div className="text-label-caps text-text-muted mb-1">Hit Ratio</div>
          <div className={`text-data-tabular tabular-nums ${statusClass(hr_status)}`}>
            {hrLabel}
          </div>
        </div>
        <div>
          <div className="text-label-caps text-text-muted mb-1">Profit Factor</div>
          <div className={`text-data-tabular tabular-nums ${statusClass(pf_status)}`}>
            {pfValue}
          </div>
        </div>
        <div>
          <div className="text-label-caps text-text-muted mb-1">Realized R/R</div>
          <div className={`text-data-tabular tabular-nums ${statusClass(rr_status)}`}>
            {rrLabel}
          </div>
        </div>
      </div>

      {summary.below_breakeven && (
        <div className="mt-2 px-2 py-1 rounded bg-error-container/30 border border-error-container text-xs font-mono text-error">
          Below break-even at R/R 3.0
        </div>
      )}
    </div>
  );
}
