import { render, screen } from "@testing-library/react";
import BetSizeCell from "@/components/BetSizeCell";

describe("BetSizeCell", () => {
  it("renders gain, loss, and EV for BUY signal with populated data", () => {
    render(
      <BetSizeCell gain={3.0} loss={1.0} ev={0.4} hrUsed={0.35} hrSrc="assumed" />
    );
    expect(screen.getByText("+$3.00")).toBeInTheDocument();
    expect(screen.getByText("-$1.00")).toBeInTheDocument();
    expect(screen.getByText(/EV \$0\.40/)).toBeInTheDocument();
    expect(screen.getByText(/35% assumed/)).toBeInTheDocument();
  });

  it("renders dash when gain is null", () => {
    render(
      <BetSizeCell gain={null} loss={null} ev={null} hrUsed={null} hrSrc={null} />
    );
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("shows assumed tooltip explaining the 35% basis", () => {
    render(
      <BetSizeCell gain={3.0} loss={1.0} ev={0.4} hrUsed={0.35} hrSrc="assumed" />
    );
    const badge = screen.getByTitle(/35% assumed hit rate/);
    expect(badge).toBeInTheDocument();
  });

  it("shows realized label and tooltip for realized hit rate", () => {
    render(
      <BetSizeCell gain={3.0} loss={1.0} ev={0.65} hrUsed={0.45} hrSrc="realized" />
    );
    expect(screen.getByText(/45% realized/)).toBeInTheDocument();
    const badge = screen.getByTitle(/realized hit rate from historical/);
    expect(badge).toBeInTheDocument();
  });

  it("renders dash for non-null gain but null loss (incomplete data)", () => {
    render(
      <BetSizeCell gain={3.0} loss={null} ev={null} hrUsed={null} hrSrc={null} />
    );
    expect(screen.getByText("—")).toBeInTheDocument();
  });
});
