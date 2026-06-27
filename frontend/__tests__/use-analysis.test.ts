import { renderHook, act, waitFor } from "@testing-library/react";
import { jest } from "@jest/globals";

const startAnalysisRun = jest.fn();
const getRunStatus = jest.fn();
const getLatestAnalysis = jest.fn();
const getLatestPartial = jest.fn();

jest.mock("@/lib/api", () => ({
  startAnalysisRun: (...a: unknown[]) => startAnalysisRun(...a),
  getRunStatus: (...a: unknown[]) => getRunStatus(...a),
  getLatestAnalysis: (...a: unknown[]) => getLatestAnalysis(...a),
  getLatestPartial: (...a: unknown[]) => getLatestPartial(...a),
  getTickerAnalysis: jest.fn(),
  addAnalysisTicker: jest.fn(),
  RunInProgressError: class RunInProgressError extends Error {
    runId: string;
    constructor(runId: string) {
      super("run_already_in_progress");
      this.runId = runId;
    }
  },
}));

import { useAnalysis } from "@/lib/use-analysis";

beforeEach(() => {
  jest.clearAllMocks();
  jest.useFakeTimers();
  getLatestAnalysis.mockResolvedValue({ results: [] });
});

afterEach(() => {
  jest.runOnlyPendingTimers();
  jest.useRealTimers();
});

describe("useAnalysis totalAnalyzed (US-401)", () => {
  it("exposes totalAnalyzed from API response", async () => {
    getLatestAnalysis.mockResolvedValue({ results: [{ ticker: "AAPL", analyzed_at: new Date().toISOString() }], total_analyzed: 42 });

    const { result } = renderHook(() => useAnalysis());
    await waitFor(() => expect(result.current.totalAnalyzed).toBe(42));
  });

  it("defaults totalAnalyzed to 0 when field absent", async () => {
    getLatestAnalysis.mockResolvedValue({ results: [] });

    const { result } = renderHook(() => useAnalysis());
    await waitFor(() => expect(result.current.status).toBeDefined());
    expect(result.current.totalAnalyzed).toBe(0);
  });
});

describe("useAnalysis polling (US-204 8.7)", () => {
  it("stops polling when stage becomes complete", async () => {
    startAnalysisRun.mockResolvedValue({
      run_id: "r1",
      tickers_total: 5,
      started_at: new Date().toISOString(),
    });
    getRunStatus
      .mockResolvedValueOnce({ stage: "data", tickers_completed: 2, tickers_total: 5, errors_so_far: [] })
      .mockResolvedValueOnce({ stage: "complete", tickers_completed: 5, tickers_total: 5, errors_so_far: [] });
    getLatestAnalysis.mockResolvedValue({ results: [] });

    const { result } = renderHook(() => useAnalysis());

    await act(async () => {
      await result.current.triggerRun();
    });

    // First poll fires immediately on start
    await waitFor(() => expect(getRunStatus).toHaveBeenCalledTimes(1));

    // Advance to the next 3s tick → second poll returns "complete" → stops
    await act(async () => {
      jest.advanceTimersByTime(3000);
    });
    await waitFor(() => expect(getRunStatus).toHaveBeenCalledTimes(2));

    const callsAfterComplete = getRunStatus.mock.calls.length;
    await act(async () => {
      jest.advanceTimersByTime(9000);
    });
    expect(getRunStatus.mock.calls.length).toBe(callsAfterComplete);
    await waitFor(() => expect(result.current.status).toBe("done"));
  });

  it("stops polling and reports error when stage becomes failed", async () => {
    startAnalysisRun.mockResolvedValue({
      run_id: "r2",
      tickers_total: 5,
      started_at: new Date().toISOString(),
    });
    getRunStatus.mockResolvedValue({
      stage: "failed",
      tickers_completed: 1,
      tickers_total: 5,
      errors_so_far: [{ ticker: "*", error_message: "boom" }],
    });

    const { result } = renderHook(() => useAnalysis());
    await act(async () => {
      await result.current.triggerRun();
    });
    await waitFor(() => expect(getRunStatus).toHaveBeenCalledTimes(1));

    const calls = getRunStatus.mock.calls.length;
    await act(async () => {
      jest.advanceTimersByTime(9000);
    });
    expect(getRunStatus.mock.calls.length).toBe(calls);
    await waitFor(() => expect(result.current.status).toBe("error"));
  });
});
