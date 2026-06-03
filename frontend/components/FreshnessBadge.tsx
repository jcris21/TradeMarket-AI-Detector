import type { FreshnessStatus } from "@/lib/types";

interface FreshnessBadgeProps {
  status: FreshnessStatus;
  ageHours: number;
}

function formatAge(hours: number): string {
  return hours < 10 ? `${hours.toFixed(1)}h ago` : `${Math.round(hours)}h ago`;
}

const BADGE_CONFIG: Record<
  FreshnessStatus,
  { icon: string; label: string; colorClass: string; tooltip: string }
> = {
  fresh: {
    icon: "✅",
    label: "Fresh",
    colorClass: "text-green-400 border-green-700",
    tooltip: "Signal is within the optimal entry window (< 2h old)",
  },
  active: {
    icon: "⚠️",
    label: "Active",
    colorClass: "text-yellow-400 border-yellow-700",
    tooltip: "Signal is 2–5h old. Verify price action before entering.",
  },
  aged: {
    icon: "⌛",
    label: "Aged",
    colorClass: "text-orange-400 border-orange-700",
    tooltip: "Signal is >5h old. Entry conditions may no longer apply.",
  },
  expired: {
    icon: "❌",
    label: "Expired",
    colorClass: "text-gray-500 border-gray-700",
    tooltip: "Signal is >24h old. Moved to Signal Archive.",
  },
};

export default function FreshnessBadge({ status, ageHours }: FreshnessBadgeProps) {
  const { icon, label, colorClass, tooltip } = BADGE_CONFIG[status];
  return (
    <span
      className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded border text-xs font-mono ${colorClass}`}
      title={tooltip}
    >
      <span>{icon}</span>
      <span>{label}</span>
      <span className="opacity-70">· {formatAge(ageHours)}</span>
    </span>
  );
}
