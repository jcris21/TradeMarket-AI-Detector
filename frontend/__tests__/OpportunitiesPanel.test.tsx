import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { jest } from "@jest/globals";
import OpportunitiesPanel from "@/components/OpportunitiesPanel";
import type { AssetAnalysis } from "@/lib/types";

// Mutable hook state controlled per-test
const mockHook = jest.fn();
jest.mock("@/lib/use-analysis", () => ({
  useAnalysis: () => mockHook(),
}));

jest.mock("@/lib/use-performance", () => ({
  usePerformance: () => ({ performance: null, isLoading: false }),
}));

const baseSignal: AssetAnalysis = {
  ticker: "NVDA",
  signal: "BUY",
  confidence: 0.85,
  entry_price: 890,
  target_price: 920,
  stop_loss: 875,
  risk_reward_ratio: 4.2,
  support_validated: true,
  indicators_summary: {},
  argument: "Strong bullish setup.",
  score: 88,
  rank: 1,
  analyzed_at: new Date().toISOString(),
};

const expiredSignal: AssetAnalysis = {
  ...baseSignal,
  ticker: "TSLA",
  freshness_status: "expired",
  freshness_age_hours: 25.0,
};

const agedSignal: AssetAnalysis = {
  ...baseSignal,
  ticker: "AAPL",
  freshness_status: "aged",
  freshness_age_hours: 7.0,
  score: 72,
};

const defaultHookState = {
  top5: [baseSignal],
  results: [],
  status: "done",
  lastAnalyzedAt: new Date().toISOString(),
  errorMessage: null,
  triggerRun: jest.fn(),
  addTicker: jest.fn(),
  getArgument: jest.fn().mockResolvedValue("Strong bullish setup."),
};

beforeEach(() => {
  mockHook.mockReturnValue(defaultHookState);
});

describe("OpportunitiesPanel", () => {
  it("renders top5 table with ticker row", () => {
    render(<OpportunitiesPanel onTickerSelect={jest.fn()} onInjectChat={jest.fn()} />);
    expect(screen.getByText("NVDA")).toBeInTheDocument();
    expect(screen.getByText("4.2x")).toBeInTheDocument();
    expect(screen.getByText("BUY")).toBeInTheDocument();
  });

  it("calls onTickerSelect and onInjectChat with argument when row is clicked", async () => {
    const onTickerSelect = jest.fn();
    const onInjectChat = jest.fn();
    render(<OpportunitiesPanel onTickerSelect={onTickerSelect} onInjectChat={onInjectChat} />);
    fireEvent.click(screen.getByText("NVDA"));
    await waitFor(() => {
      expect(onTickerSelect).toHaveBeenCalledWith("NVDA");
      expect(onInjectChat).toHaveBeenCalledWith(expect.stringContaining("NVDA"));
    });
  });

  it("calls onInjectChat without argument when getArgument returns null", async () => {
    mockHook.mockReturnValue({
      ...defaultHookState,
      getArgument: jest.fn().mockResolvedValue(null),
    });
    const onInjectChat = jest.fn();
    render(<OpportunitiesPanel onTickerSelect={jest.fn()} onInjectChat={onInjectChat} />);
    fireEvent.click(screen.getByText("NVDA"));
    await waitFor(() => {
      expect(onInjectChat).toHaveBeenCalledWith("Muéstrame el análisis técnico de NVDA");
    });
  });

  it("shows idle message when status is idle and no results", () => {
    mockHook.mockReturnValue({ ...defaultHookState, top5: [], results: [], status: "idle" });
    render(<OpportunitiesPanel onTickerSelect={jest.fn()} onInjectChat={jest.fn()} />);
    expect(screen.getByText(/Presiona/i)).toBeInTheDocument();
  });

  it("shows error banner when errorMessage is set", () => {
    mockHook.mockReturnValue({ ...defaultHookState, errorMessage: "Analysis failed" });
    render(<OpportunitiesPanel onTickerSelect={jest.fn()} onInjectChat={jest.fn()} />);
    expect(screen.getByText("Analysis failed")).toBeInTheDocument();
  });

  it("renders FreshnessBadge for signals with freshness data", () => {
    mockHook.mockReturnValue({
      ...defaultHookState,
      results: [{ ...baseSignal, freshness_status: "fresh", freshness_age_hours: 1.5 }],
    });
    render(<OpportunitiesPanel onTickerSelect={jest.fn()} onInjectChat={jest.fn()} />);
    expect(screen.getByText("Fresh")).toBeInTheDocument();
    expect(screen.getByText("· 1.5h ago")).toBeInTheDocument();
  });

  it("renders dash in freshness cell when freshness data is absent", () => {
    render(<OpportunitiesPanel onTickerSelect={jest.fn()} onInjectChat={jest.fn()} />);
    // baseSignal has no freshness_status — should show '—'
    const dashes = screen.getAllByText("—");
    expect(dashes.length).toBeGreaterThan(0);
  });

  it("switches to Archivo tab when clicked and shows expired signals", () => {
    mockHook.mockReturnValue({
      ...defaultHookState,
      results: [baseSignal, expiredSignal],
    });
    render(<OpportunitiesPanel onTickerSelect={jest.fn()} onInjectChat={jest.fn()} />);
    // TSLA is expired — should NOT be visible in default tab
    expect(screen.queryByText("TSLA")).not.toBeInTheDocument();
    fireEvent.click(screen.getByText(/Archivo/));
    expect(screen.getByText("TSLA")).toBeInTheDocument();
  });

  it("shows empty archive message when no expired signals exist", () => {
    mockHook.mockReturnValue({ ...defaultHookState, results: [baseSignal] });
    render(<OpportunitiesPanel onTickerSelect={jest.fn()} onInjectChat={jest.fn()} />);
    fireEvent.click(screen.getByText(/Archivo/));
    expect(screen.getByText(/No hay señales expiradas/i)).toBeInTheDocument();
  });

  it("filters expired signals out of Oportunidades tab", () => {
    mockHook.mockReturnValue({
      ...defaultHookState,
      results: [baseSignal, expiredSignal],
    });
    render(<OpportunitiesPanel onTickerSelect={jest.fn()} onInjectChat={jest.fn()} />);
    expect(screen.getByText("NVDA")).toBeInTheDocument();
    expect(screen.queryByText("TSLA")).not.toBeInTheDocument();
  });

  it("shows archive count badge when expired signals exist", () => {
    mockHook.mockReturnValue({
      ...defaultHookState,
      results: [baseSignal, expiredSignal],
    });
    render(<OpportunitiesPanel onTickerSelect={jest.fn()} onInjectChat={jest.fn()} />);
    const archiveButton = screen.getByRole("button", { name: /Archivo/ });
    expect(archiveButton.textContent).toContain("(1)");
  });

  it("dims score cell for aged signals", () => {
    mockHook.mockReturnValue({ ...defaultHookState, results: [agedSignal] });
    render(<OpportunitiesPanel onTickerSelect={jest.fn()} onInjectChat={jest.fn()} />);
    // The score cell for aged should have opacity-40 class
    const cells = document.querySelectorAll("td.opacity-40");
    expect(cells.length).toBeGreaterThan(0);
  });

  it("adds a ticker when button is clicked", async () => {
    const addTicker = jest.fn().mockResolvedValue(undefined);
    mockHook.mockReturnValue({ ...defaultHookState, addTicker });
    render(<OpportunitiesPanel onTickerSelect={jest.fn()} onInjectChat={jest.fn()} />);
    fireEvent.change(screen.getByPlaceholderText(/Agregar ticker/i), {
      target: { value: "PYPL" },
    });
    fireEvent.click(screen.getByText("Agregar"));
    await waitFor(() => {
      expect(addTicker).toHaveBeenCalledWith("PYPL");
    });
  });

  it("shows error message when addTicker throws", async () => {
    const addTicker = jest.fn().mockRejectedValue(new Error("Not found"));
    mockHook.mockReturnValue({ ...defaultHookState, addTicker });
    render(<OpportunitiesPanel onTickerSelect={jest.fn()} onInjectChat={jest.fn()} />);
    fireEvent.change(screen.getByPlaceholderText(/Agregar ticker/i), {
      target: { value: "FAKE" },
    });
    fireEvent.click(screen.getByText("Agregar"));
    await waitFor(() => {
      expect(screen.getByText(/No se pudo agregar FAKE/i)).toBeInTheDocument();
    });
  });

  it("shows empty SignalTable message when archive has signals but none in active view", () => {
    // All results are expired → activeSignals is empty → empty state in Oportunidades
    mockHook.mockReturnValue({
      ...defaultHookState,
      top5: [],
      results: [expiredSignal],
      status: "done",
    });
    render(<OpportunitiesPanel onTickerSelect={jest.fn()} onInjectChat={jest.fn()} />);
    expect(screen.getByText(/ratio/i)).toBeInTheDocument();
  });
});
