import { render, screen } from "@testing-library/react";
import PerformanceSummaryPanel from "@/components/PerformanceSummaryPanel";
import type { PerformanceSummary } from "@/lib/types";

const calibrationSummary: PerformanceSummary = {
  phase_gate_active: true,
  calibration_count: 15,
  total_signals: 15,
  target_hits: 10,
  stop_hits: 5,
  expired: 0,
  orphaned_count: 0,
  hit_ratio: null,
  profit_factor: null,
  realized_rr: null,
  hr_status: null,
  pf_status: null,
  rr_status: null,
  below_breakeven: false,
};

const metricsSummary: PerformanceSummary = {
  phase_gate_active: false,
  calibration_count: 60,
  total_signals: 70,
  target_hits: 40,
  stop_hits: 20,
  expired: 10,
  orphaned_count: 0,
  hit_ratio: 0.6667,
  profit_factor: 2.18,
  realized_rr: 2.5,
  hr_status: "green",
  pf_status: "green",
  rr_status: "green",
  below_breakeven: false,
};

const belowBreakevenSummary: PerformanceSummary = {
  ...metricsSummary,
  hit_ratio: 0.2,
  hr_status: "red",
  below_breakeven: true,
};

const pfRedSummary: PerformanceSummary = {
  ...metricsSummary,
  profit_factor: 0.8,
  pf_status: "red",
};

const pfInfinitySummary: PerformanceSummary = {
  ...metricsSummary,
  profit_factor: 999.0,
  pf_status: "green",
};

describe("PerformanceSummaryPanel — calibration state", () => {
  it("shows Phase 0 Calibration text and count", () => {
    render(<PerformanceSummaryPanel summary={calibrationSummary} />);
    expect(screen.getByText(/Phase 0 — Calibration/)).toBeInTheDocument();
    expect(screen.getByText("15/30 signals")).toBeInTheDocument();
  });

  it("does not render metric rows in calibration state", () => {
    render(<PerformanceSummaryPanel summary={calibrationSummary} />);
    expect(screen.queryByText("Hit Ratio")).not.toBeInTheDocument();
    expect(screen.queryByText("Profit Factor")).not.toBeInTheDocument();
    expect(screen.queryByText("Realized R/R")).not.toBeInTheDocument();
  });
});

describe("PerformanceSummaryPanel — metrics state", () => {
  it("renders all 3 metric labels", () => {
    render(<PerformanceSummaryPanel summary={metricsSummary} />);
    expect(screen.getByText("Hit Ratio")).toBeInTheDocument();
    expect(screen.getByText("Profit Factor")).toBeInTheDocument();
    expect(screen.getByText("Realized R/R")).toBeInTheDocument();
  });

  it("applies green class to Hit Ratio when hr_status is green", () => {
    render(<PerformanceSummaryPanel summary={metricsSummary} />);
    const hrValue = screen.getByText(/67%/);
    expect(hrValue).toHaveClass("text-green-400");
  });

  it("applies red class to Hit Ratio when hr_status is red", () => {
    render(<PerformanceSummaryPanel summary={belowBreakevenSummary} />);
    const hrValue = screen.getByText(/20%/);
    expect(hrValue).toHaveClass("text-red-400");
  });

  it("applies green class to Profit Factor when pf_status is green", () => {
    render(<PerformanceSummaryPanel summary={metricsSummary} />);
    const pfValue = screen.getByText("2.18");
    expect(pfValue).toHaveClass("text-green-400");
  });

  it("applies red class to Profit Factor when pf_status is red", () => {
    render(<PerformanceSummaryPanel summary={pfRedSummary} />);
    const pfValue = screen.getByText("0.80");
    expect(pfValue).toHaveClass("text-red-400");
  });
});

describe("PerformanceSummaryPanel — break-even warning", () => {
  it("shows warning when below_breakeven is true", () => {
    render(<PerformanceSummaryPanel summary={belowBreakevenSummary} />);
    expect(screen.getByText(/Below break-even at R\/R 3\.0/)).toBeInTheDocument();
  });

  it("does not show warning when below_breakeven is false", () => {
    render(<PerformanceSummaryPanel summary={metricsSummary} />);
    expect(screen.queryByText(/Below break-even/)).not.toBeInTheDocument();
  });
});

describe("PerformanceSummaryPanel — profit_factor sentinel", () => {
  it("renders 999.0 as infinity symbol", () => {
    render(<PerformanceSummaryPanel summary={pfInfinitySummary} />);
    expect(screen.getByText("∞")).toBeInTheDocument();
  });
});
