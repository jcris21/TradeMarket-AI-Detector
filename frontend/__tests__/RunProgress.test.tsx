import { render, screen } from "@testing-library/react";
import { jest } from "@jest/globals";
import OpportunitiesPanel from "@/components/OpportunitiesPanel";
import type { RunStatus } from "@/lib/types";

const mockHook = jest.fn();
jest.mock("@/lib/use-analysis", () => ({
  useAnalysis: () => mockHook(),
}));
jest.mock("@/lib/use-performance", () => ({
  usePerformance: () => ({ performance: null, isLoading: false }),
}));

const runStatus: RunStatus = {
  run_id: "r1",
  stage: "data",
  tickers_total: 100,
  tickers_completed: 42,
  errors_so_far: [],
  started_at: new Date().toISOString(),
  completed_at: null,
  estimated_remaining_seconds: 18,
};

const runningHookState = {
  top5: [],
  results: [],
  status: "running",
  runStatus,
  previewResults: [],
  lastAnalyzedAt: null,
  errorMessage: null,
  triggerRun: jest.fn(),
  loadPreview: jest.fn(),
  addTicker: jest.fn(),
  getArgument: jest.fn(),
};

describe("RunProgress (US-204 8.6)", () => {
  it("renders progress bar filled to 42% for 42/100", () => {
    mockHook.mockReturnValue(runningHookState);
    render(<OpportunitiesPanel onTickerSelect={jest.fn()} onInjectChat={jest.fn()} />);
    const fill = screen.getByTestId("progress-bar-fill");
    expect(fill).toHaveStyle({ width: "42%" });
  });

  it("renders the DATA stage badge while in data stage", () => {
    mockHook.mockReturnValue(runningHookState);
    render(<OpportunitiesPanel onTickerSelect={jest.fn()} onInjectChat={jest.fn()} />);
    expect(screen.getByText("DATA")).toBeInTheDocument();
  });

  it("renders the ETA label when estimated_remaining_seconds is present", () => {
    mockHook.mockReturnValue(runningHookState);
    render(<OpportunitiesPanel onTickerSelect={jest.fn()} onInjectChat={jest.fn()} />);
    expect(screen.getByTestId("run-eta")).toHaveTextContent("~18s remaining");
  });

  it("hides the ETA label when estimated_remaining_seconds is null", () => {
    mockHook.mockReturnValue({
      ...runningHookState,
      runStatus: { ...runStatus, tickers_completed: 0, estimated_remaining_seconds: null },
    });
    render(<OpportunitiesPanel onTickerSelect={jest.fn()} onInjectChat={jest.fn()} />);
    expect(screen.queryByTestId("run-eta")).not.toBeInTheDocument();
  });

  it("shows error count badge when errors_so_far is non-empty", () => {
    mockHook.mockReturnValue({
      ...runningHookState,
      runStatus: {
        ...runStatus,
        errors_so_far: [{ ticker: "XYZ", error_message: "boom" }],
      },
    });
    render(<OpportunitiesPanel onTickerSelect={jest.fn()} onInjectChat={jest.fn()} />);
    expect(screen.getByTestId("run-error-badge")).toHaveTextContent("1 err");
  });

  it("shows failed banner when stage is failed", () => {
    mockHook.mockReturnValue({
      ...runningHookState,
      status: "error",
      runStatus: {
        ...runStatus,
        stage: "failed",
        errors_so_far: [{ ticker: "*", error_message: "pipeline crashed" }],
      },
    });
    render(<OpportunitiesPanel onTickerSelect={jest.fn()} onInjectChat={jest.fn()} />);
    expect(screen.getByText("Analysis failed")).toBeInTheDocument();
    expect(screen.getByText(/pipeline crashed/)).toBeInTheDocument();
  });
});
