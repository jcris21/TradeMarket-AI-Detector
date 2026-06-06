import { render, screen } from "@testing-library/react";
import FreshnessBadge from "@/components/FreshnessBadge";

describe("FreshnessBadge", () => {
  it("renders fresh state with correct icon, label, age, and tooltip", () => {
    const { container } = render(<FreshnessBadge status="fresh" ageHours={1.5} />);
    expect(screen.getByText("✅")).toBeInTheDocument();
    expect(screen.getByText("Fresh")).toBeInTheDocument();
    expect(screen.getByText("· 1.5h ago")).toBeInTheDocument();
    const badge = container.firstChild as HTMLElement;
    expect(badge.title).toContain("optimal entry window");
    expect(badge.className).toContain("text-green-400");
    expect(badge.className).not.toContain("opacity-40");
  });

  it("renders active state with correct icon, label, age, and tooltip", () => {
    const { container } = render(<FreshnessBadge status="active" ageHours={3.0} />);
    expect(screen.getByText("⚠️")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
    expect(screen.getByText("· 3.0h ago")).toBeInTheDocument();
    const badge = container.firstChild as HTMLElement;
    expect(badge.title).toContain("Verify");
    expect(badge.className).toContain("text-yellow-400");
    expect(badge.className).not.toContain("opacity-40");
  });

  it("renders aged state with correct icon, label, age, and tooltip", () => {
    const { container } = render(<FreshnessBadge status="aged" ageHours={7.0} />);
    expect(screen.getByText("⌛")).toBeInTheDocument();
    expect(screen.getByText("Aged")).toBeInTheDocument();
    expect(screen.getByText("· 7.0h ago")).toBeInTheDocument();
    const badge = container.firstChild as HTMLElement;
    expect(badge.title).toContain("no longer apply");
    expect(badge.className).toContain("text-orange-400");
  });

  it("renders expired state with correct icon, label, age, and tooltip", () => {
    const { container } = render(<FreshnessBadge status="expired" ageHours={25.0} />);
    expect(screen.getByText("❌")).toBeInTheDocument();
    expect(screen.getByText("Expired")).toBeInTheDocument();
    expect(screen.getByText("· 25h ago")).toBeInTheDocument();
    const badge = container.firstChild as HTMLElement;
    expect(badge.title).toContain("Signal Archive");
    expect(badge.className).toContain("text-gray-500");
  });

  it("formats age as integer when >= 10 hours", () => {
    render(<FreshnessBadge status="expired" ageHours={12.7} />);
    expect(screen.getByText("· 13h ago")).toBeInTheDocument();
  });

  it("formats age with 1 decimal when < 10 hours", () => {
    render(<FreshnessBadge status="fresh" ageHours={0.5} />);
    expect(screen.getByText("· 0.5h ago")).toBeInTheDocument();
  });
});
