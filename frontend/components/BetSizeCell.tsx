interface BetSizeCellProps {
  gain: number | null;
  loss: number | null;
  ev: number | null;
  hrUsed: number | null;
  hrSrc: string | null;
}

export default function BetSizeCell({ gain, loss, ev, hrUsed, hrSrc }: BetSizeCellProps) {
  if (gain === null || loss === null || ev === null || hrUsed === null || hrSrc === null) {
    return <span className="text-text-muted">—</span>;
  }

  const pct = Math.round(hrUsed * 100);
  const tooltip =
    hrSrc === "assumed"
      ? `Per $100 risked — based on 35% assumed hit rate (< 30 historical signals)`
      : `Per $100 risked — based on realized hit rate from historical signal outcomes`;

  return (
    <div className="flex flex-col gap-0.5 font-mono tabular-nums text-xs">
      <span className="text-green-400 font-bold">+${gain.toFixed(2)}</span>
      <span className="text-red-400">-${loss.toFixed(2)}</span>
      <span className="text-accent-yellow" title={tooltip}>
        EV ${ev.toFixed(2)}/$100 @ {pct}% {hrSrc}
      </span>
    </div>
  );
}
