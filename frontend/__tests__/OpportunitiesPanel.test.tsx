import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { jest } from "@jest/globals";
import OpportunitiesPanel from "@/components/OpportunitiesPanel";

// Mock the hook
jest.mock("@/lib/use-analysis", () => ({
  useAnalysis: () => ({
    top5: [
      {
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
      },
    ],
    results: [],
    status: "done",
    lastAnalyzedAt: new Date().toISOString(),
    errorMessage: null,
    triggerRun: jest.fn(),
    addTicker: jest.fn(),
    getArgument: jest.fn().mockResolvedValue("Strong bullish setup."),
  }),
}));

describe("OpportunitiesPanel", () => {
  it("renders top5 table with ticker row", () => {
    render(
      <OpportunitiesPanel
        onTickerSelect={jest.fn()}
        onInjectChat={jest.fn()}
      />
    );
    expect(screen.getByText("NVDA")).toBeInTheDocument();
    expect(screen.getByText("4.2x")).toBeInTheDocument();
    expect(screen.getByText("BUY")).toBeInTheDocument();
  });

  it("calls onTickerSelect and onInjectChat when row is clicked", async () => {
    const onTickerSelect = jest.fn();
    const onInjectChat = jest.fn();
    render(
      <OpportunitiesPanel
        onTickerSelect={onTickerSelect}
        onInjectChat={onInjectChat}
      />
    );
    fireEvent.click(screen.getByText("NVDA"));
    await waitFor(() => {
      expect(onTickerSelect).toHaveBeenCalledWith("NVDA");
      expect(onInjectChat).toHaveBeenCalledWith(expect.stringContaining("NVDA"));
    });
  });

  it("shows idle message when status is idle and no top5", () => {
    const { useAnalysis } = jest.requireMock("@/lib/use-analysis") as any;
    const original = useAnalysis();
    jest.spyOn(
      jest.requireMock("@/lib/use-analysis"),
      "useAnalysis"
    ).mockReturnValue({ ...original, top5: [], status: "idle" });

    render(
      <OpportunitiesPanel onTickerSelect={jest.fn()} onInjectChat={jest.fn()} />
    );
    expect(screen.getByText(/Presiona/i)).toBeInTheDocument();
  });
});
