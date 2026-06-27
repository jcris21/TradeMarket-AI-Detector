import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { jest } from "@jest/globals";
import OpportunitiesPanel, {
  getScoreBand,
  formatAge,
  BAND_COLORS,
} from "@/components/OpportunitiesPanel";
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
  totalAnalyzed: 0,
  status: "done",
  runStatus: null,
  previewResults: [],
  lastAnalyzedAt: new Date().toISOString(),
  errorMessage: null,
  regimeGateActive: false,
  vixValue: null,
  triggerRun: jest.fn(),
  loadPreview: jest.fn(),
  addTicker: jest.fn(),
  getArgument: jest.fn().mockResolvedValue("Strong bullish setup."),
  refreshTicker: jest.fn().mockResolvedValue(undefined),
};

beforeEach(() => {
  mockHook.mockReturnValue(defaultHookState);
  localStorage.clear();
});

// ── getScoreBand boundary tests (task 8.4) ────────────────────────────────────

describe("getScoreBand", () => {
  it("returns ELITE for score >= 75", () => {
    expect(getScoreBand(75)).toBe("ELITE");
    expect(getScoreBand(80)).toBe("ELITE");
    expect(getScoreBand(100)).toBe("ELITE");
  });

  it("returns STRONG for score 60–74", () => {
    expect(getScoreBand(60)).toBe("STRONG");
    expect(getScoreBand(67)).toBe("STRONG");
    expect(getScoreBand(74.9)).toBe("STRONG");
  });

  it("returns QUALIFYING for score 50–59", () => {
    expect(getScoreBand(50)).toBe("QUALIFYING");
    expect(getScoreBand(52)).toBe("QUALIFYING");
    expect(getScoreBand(59.9)).toBe("QUALIFYING");
  });

  it("returns NONE for score < 50", () => {
    expect(getScoreBand(49.9)).toBe("NONE");
    expect(getScoreBand(0)).toBe("NONE");
  });

  it("returns NONE for null/undefined", () => {
    expect(getScoreBand(null)).toBe("NONE");
    expect(getScoreBand(undefined)).toBe("NONE");
  });
});

// ── BAND_COLORS constant (task 8.4 helper) ────────────────────────────────────

describe("BAND_COLORS", () => {
  it("maps ELITE to #ECAD0A", () => expect(BAND_COLORS.ELITE).toBe("#ECAD0A"));
  it("maps STRONG to #209DD7", () => expect(BAND_COLORS.STRONG).toBe("#209DD7"));
  it("maps QUALIFYING to #888888", () => expect(BAND_COLORS.QUALIFYING).toBe("#888888"));
  it("maps NONE to #444444", () => expect(BAND_COLORS.NONE).toBe("#444444"));
});

// ── formatAge utility tests (task 8.5) ────────────────────────────────────────

describe("formatAge", () => {
  it("shows Xm ago for under 60 minutes", () => {
    const now = Date.now();
    const analyzedAt = new Date(now - 30 * 60_000).toISOString();
    expect(formatAge(analyzedAt, now)).toBe("30m ago");
  });

  it("shows Xh Ym ago for 60+ minutes", () => {
    const now = Date.now();
    const analyzedAt = new Date(now - 90 * 60_000).toISOString();
    expect(formatAge(analyzedAt, now)).toBe("1h 30m ago");
  });

  it("omits minutes when exactly on the hour", () => {
    const now = Date.now();
    const analyzedAt = new Date(now - 2 * 60 * 60_000).toISOString();
    expect(formatAge(analyzedAt, now)).toBe("2h ago");
  });

  it("shows 0m ago for very recent signal", () => {
    const now = Date.now();
    const analyzedAt = new Date(now - 10_000).toISOString();
    expect(formatAge(analyzedAt, now)).toBe("0m ago");
  });
});

// ── OpportunitiesPanel component tests ───────────────────────────────────────

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

  // ── US-402: Collapse (task 8.6 / panel tests) ──────────────────────────────

  it("collapses body when header is clicked", () => {
    render(<OpportunitiesPanel onTickerSelect={jest.fn()} onInjectChat={jest.fn()} />);
    const header = screen.getByText(/TOP OPORTUNIDADES/);
    fireEvent.click(header);
    // After collapse, chevron changes to ▶
    expect(screen.getByText(/▶/)).toBeInTheDocument();
  });

  it("persists collapsed state in localStorage", () => {
    render(<OpportunitiesPanel onTickerSelect={jest.fn()} onInjectChat={jest.fn()} />);
    const header = screen.getByText(/TOP OPORTUNIDADES/);
    fireEvent.click(header);
    expect(localStorage.getItem("finally_top_opps_collapsed")).toBe("true");
  });

  it("initialises collapsed from localStorage", () => {
    localStorage.setItem("finally_top_opps_collapsed", "true");
    render(<OpportunitiesPanel onTickerSelect={jest.fn()} onInjectChat={jest.fn()} />);
    expect(screen.getByText(/▶/)).toBeInTheDocument();
  });

  it("shows collapsed signal count badge when collapsed", () => {
    mockHook.mockReturnValue({ ...defaultHookState, top5: [baseSignal], results: [] });
    localStorage.setItem("finally_top_opps_collapsed", "true");
    render(<OpportunitiesPanel onTickerSelect={jest.fn()} onInjectChat={jest.fn()} />);
    expect(screen.getByText("[1]")).toBeInTheDocument();
  });

  // ── US-401: Pagination (task 8.9) ──────────────────────────────────────────

  it("hides pagination controls when 10 or fewer signals", () => {
    const signals = Array.from({ length: 8 }, (_, i) => ({ ...baseSignal, ticker: `T${i}`, rank: i + 1 }));
    mockHook.mockReturnValue({ ...defaultHookState, top5: signals, results: [] });
    render(<OpportunitiesPanel onTickerSelect={jest.fn()} onInjectChat={jest.fn()} />);
    expect(screen.queryByText(/← Prev/)).not.toBeInTheDocument();
  });

  it("shows pagination controls when more than 10 signals", () => {
    const signals = Array.from({ length: 15 }, (_, i) => ({
      ...baseSignal,
      ticker: `T${i}`,
      rank: i + 1,
    }));
    mockHook.mockReturnValue({ ...defaultHookState, top5: signals, results: [] });
    render(<OpportunitiesPanel onTickerSelect={jest.fn()} onInjectChat={jest.fn()} />);
    expect(screen.getByText("← Prev")).toBeInTheDocument();
    expect(screen.getByText("Next →")).toBeInTheDocument();
    expect(screen.getByText(/Page 1 of 2/)).toBeInTheDocument();
  });

  it("Prev button is disabled on first page", () => {
    const signals = Array.from({ length: 15 }, (_, i) => ({
      ...baseSignal,
      ticker: `T${i}`,
      rank: i + 1,
    }));
    mockHook.mockReturnValue({ ...defaultHookState, top5: signals, results: [] });
    render(<OpportunitiesPanel onTickerSelect={jest.fn()} onInjectChat={jest.fn()} />);
    const prevBtn = screen.getByText("← Prev");
    expect(prevBtn).toBeDisabled();
  });

  it("Next button is disabled on last page", () => {
    const signals = Array.from({ length: 15 }, (_, i) => ({
      ...baseSignal,
      ticker: `T${i}`,
      rank: i + 1,
    }));
    mockHook.mockReturnValue({ ...defaultHookState, top5: signals, results: [] });
    render(<OpportunitiesPanel onTickerSelect={jest.fn()} onInjectChat={jest.fn()} />);
    fireEvent.click(screen.getByText("Next →"));
    expect(screen.getByText("Next →")).toBeDisabled();
  });

  // ── US-403: ScoreBandBadge rendered (task 8.6) ────────────────────────────

  it("renders ELITE badge for score >= 75", () => {
    mockHook.mockReturnValue({
      ...defaultHookState,
      top5: [{ ...baseSignal, score_quant: 82 }],
    });
    render(<OpportunitiesPanel onTickerSelect={jest.fn()} onInjectChat={jest.fn()} />);
    expect(screen.getByText("ELITE")).toBeInTheDocument();
  });

  it("does not render badge for NONE band", () => {
    mockHook.mockReturnValue({
      ...defaultHookState,
      top5: [{ ...baseSignal, score_quant: 40 }],
    });
    render(<OpportunitiesPanel onTickerSelect={jest.fn()} onInjectChat={jest.fn()} />);
    expect(screen.queryByText("NONE")).not.toBeInTheDocument();
  });

  // ── US-404: Expired row styling in archive tab ────────────────────────────

  it("shows EXPIRED badge in archive tab and not ScoreBandBadge", () => {
    mockHook.mockReturnValue({
      ...defaultHookState,
      results: [{ ...expiredSignal, score_quant: 80, freshness_status: "expired" }],
    });
    render(<OpportunitiesPanel onTickerSelect={jest.fn()} onInjectChat={jest.fn()} />);
    fireEvent.click(screen.getByText(/Archivo/));
    expect(screen.getByText("EXPIRED")).toBeInTheDocument();
    expect(screen.queryByText("ELITE")).not.toBeInTheDocument();
  });

  // ── Summary line ──────────────────────────────────────────────────────────

  it("shows summary line with signal count", () => {
    render(<OpportunitiesPanel onTickerSelect={jest.fn()} onInjectChat={jest.fn()} />);
    expect(screen.getByText(/Showing 1 of 1 qualified signals/)).toBeInTheDocument();
  });

  it("includes analyzed count when totalAnalyzed > 0", () => {
    mockHook.mockReturnValue({ ...defaultHookState, totalAnalyzed: 50 });
    render(<OpportunitiesPanel onTickerSelect={jest.fn()} onInjectChat={jest.fn()} />);
    expect(screen.getByText(/50 analyzed/)).toBeInTheDocument();
  });

  it("omits analyzed count when totalAnalyzed is 0", () => {
    mockHook.mockReturnValue({ ...defaultHookState, totalAnalyzed: 0 });
    render(<OpportunitiesPanel onTickerSelect={jest.fn()} onInjectChat={jest.fn()} />);
    expect(screen.queryByText(/analyzed/)).not.toBeInTheDocument();
  });
});
