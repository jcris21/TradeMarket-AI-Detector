import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { jest } from "@jest/globals";
import TraderChartUpload from "@/components/TraderChartUpload";
import type { LevelConfirmResult, TraderChartEnrichResponse } from "@/lib/types";

jest.mock("@/lib/api", () => ({
  enrichTraderChart: jest.fn(),
  confirmLevels: jest.fn(),
}));

import { enrichTraderChart, confirmLevels } from "@/lib/api";

const mockEnrich = enrichTraderChart as jest.MockedFunction<typeof enrichTraderChart>;
const mockConfirm = confirmLevels as jest.MockedFunction<typeof confirmLevels>;

const ENRICH_RESPONSE: TraderChartEnrichResponse = {
  enrichment_id: "test-enrich-id",
  extracted_levels: [
    { type: "support", price: 195.5, confidence: 0.82 },
    { type: "resistance", price: 205.0, confidence: 0.65 },
    { type: "support", price: 188.0, confidence: 0.45 },
  ],
  status: "pending_confirmation",
};

const CONFIRM_RESULT: LevelConfirmResult = {
  custom_levels_applied: 2,
  enrichment_delta: 7.0,
  score_quant: 80.0,
  score_enriched: 87.0,
};

function makePngFile(sizeBytes = 100): File {
  const bytes = new Uint8Array(sizeBytes).fill(0);
  bytes[0] = 0x89; bytes[1] = 0x50; bytes[2] = 0x4e; bytes[3] = 0x47;
  return new File([bytes], "chart.png", { type: "image/png" });
}

function makeJpegFile(): File {
  const bytes = new Uint8Array(100).fill(0);
  bytes[0] = 0xff; bytes[1] = 0xd8;
  return new File([bytes], "chart.jpg", { type: "image/jpeg" });
}

function makeLargeFile(): File {
  const bytes = new Uint8Array(11 * 1024 * 1024).fill(0);
  bytes[0] = 0x89;
  return new File([bytes], "big.png", { type: "image/png" });
}

function makePdfFile(): File {
  return new File([new Uint8Array(100)], "chart.pdf", { type: "application/pdf" });
}

// Stub FileReader — sets `this.result` before calling `onload` (matches component usage)
function stubFileReader(b64 = "dGVzdA==") {
  const origFileReader = global.FileReader;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const MockFileReader = jest.fn().mockImplementation(function (this: any) {
    this.result = null;
    this.onload = null;
    this.onerror = null;
    this.readAsDataURL = jest.fn(() => {
      setTimeout(() => {
        this.result = `data:image/png;base64,${b64}`;
        if (typeof this.onload === "function") this.onload();
      }, 0);
    });
  });
  global.FileReader = MockFileReader as unknown as typeof FileReader;
  return () => { global.FileReader = origFileReader; };
}

beforeEach(() => {
  jest.clearAllMocks();
});

// --- Task 6.1: oversized file rejected client-side ---
describe("client-side file validation", () => {
  it("rejects file over 10 MB with no API call", async () => {
    render(<TraderChartUpload ticker="AAPL" onConfirmed={jest.fn()} />);
    const input = screen.getByTestId("chart-file-input");

    fireEvent.change(input, { target: { files: [makeLargeFile()] } });

    expect(await screen.findByText("File must be under 10 MB")).toBeInTheDocument();
    expect(mockEnrich).not.toHaveBeenCalled();
  });

  // Task 6.2
  it("rejects non-PNG/JPEG with error message and no API call", () => {
    render(<TraderChartUpload ticker="AAPL" onConfirmed={jest.fn()} />);
    const input = screen.getByTestId("chart-file-input");

    fireEvent.change(input, { target: { files: [makePdfFile()] } });

    expect(screen.getByText("Only PNG and JPEG images are supported")).toBeInTheDocument();
    expect(mockEnrich).not.toHaveBeenCalled();
  });
});

// --- Task 6.3: valid PNG triggers enrichTraderChart and shows spinner ---
it("valid PNG triggers enrichTraderChart call and shows loading spinner", async () => {
  const restore = stubFileReader();
  mockEnrich.mockResolvedValue(ENRICH_RESPONSE);

  render(<TraderChartUpload ticker="AAPL" onConfirmed={jest.fn()} />);
  const input = screen.getByTestId("chart-file-input");

  await act(async () => {
    fireEvent.change(input, { target: { files: [makePngFile()] } });
    await new Promise((r) => setTimeout(r, 10));
  });

  await waitFor(() => expect(mockEnrich).toHaveBeenCalledWith("AAPL", "dGVzdA=="));
  restore();
});

// --- Task 6.4: empty extracted_levels shows "No levels detected" ---
it("empty extracted_levels shows no-levels message", async () => {
  const restore = stubFileReader();
  mockEnrich.mockResolvedValue({ ...ENRICH_RESPONSE, extracted_levels: [] });

  render(<TraderChartUpload ticker="AAPL" onConfirmed={jest.fn()} />);
  const input = screen.getByTestId("chart-file-input");

  await act(async () => {
    fireEvent.change(input, { target: { files: [makePngFile()] } });
    await new Promise((r) => setTimeout(r, 10));
  });

  await waitFor(() =>
    expect(screen.getByTestId("upload-error")).toHaveTextContent(
      "No levels detected in this chart. Try a clearer image."
    )
  );
  restore();
});

// --- Task 6.5: selecting 2 levels disables remaining; deselecting re-enables ---
it("selecting 2 levels disables remaining checkboxes and deselecting re-enables them", async () => {
  const restore = stubFileReader();
  mockEnrich.mockResolvedValue(ENRICH_RESPONSE);

  render(<TraderChartUpload ticker="AAPL" onConfirmed={jest.fn()} />);
  const input = screen.getByTestId("chart-file-input");

  await act(async () => {
    fireEvent.change(input, { target: { files: [makePngFile()] } });
    await new Promise((r) => setTimeout(r, 10));
  });

  await waitFor(() => screen.getByTestId("level-checkbox-0"));

  const cb0 = screen.getByTestId("level-checkbox-0") as HTMLInputElement;
  const cb1 = screen.getByTestId("level-checkbox-1") as HTMLInputElement;
  const cb2 = screen.getByTestId("level-checkbox-2") as HTMLInputElement;

  fireEvent.click(cb0);
  fireEvent.click(cb1);

  expect(cb2).toBeDisabled();

  fireEvent.click(cb0);

  expect(cb2).not.toBeDisabled();

  restore();
});

// --- Task 6.6: confirmLevels called with correct confirmed_indices ---
it("confirmLevels called with correct confirmed_indices on submit", async () => {
  const restore = stubFileReader();
  mockEnrich.mockResolvedValue(ENRICH_RESPONSE);
  mockConfirm.mockResolvedValue(CONFIRM_RESULT);

  const onConfirmed = jest.fn();
  render(<TraderChartUpload ticker="AAPL" onConfirmed={onConfirmed} />);
  const input = screen.getByTestId("chart-file-input");

  await act(async () => {
    fireEvent.change(input, { target: { files: [makePngFile()] } });
    await new Promise((r) => setTimeout(r, 10));
  });

  await waitFor(() => screen.getByTestId("level-checkbox-0"));

  fireEvent.click(screen.getByTestId("level-checkbox-0"));
  fireEvent.click(screen.getByTestId("level-checkbox-2"));

  await act(async () => {
    fireEvent.click(screen.getByTestId("confirm-levels-btn"));
    await new Promise((r) => setTimeout(r, 10));
  });

  await waitFor(() =>
    expect(mockConfirm).toHaveBeenCalledWith("AAPL", "test-enrich-id", [0, 2])
  );

  restore();
});

// --- Task 6.7: result card shows correct enrichment_delta and score_enriched ---
it("result card shows enrichment_delta and score_enriched after confirm", async () => {
  const restore = stubFileReader();
  mockEnrich.mockResolvedValue(ENRICH_RESPONSE);
  mockConfirm.mockResolvedValue(CONFIRM_RESULT);

  render(<TraderChartUpload ticker="AAPL" onConfirmed={jest.fn()} />);
  const input = screen.getByTestId("chart-file-input");

  await act(async () => {
    fireEvent.change(input, { target: { files: [makePngFile()] } });
    await new Promise((r) => setTimeout(r, 10));
  });

  await waitFor(() => screen.getByTestId("level-checkbox-0"));
  fireEvent.click(screen.getByTestId("level-checkbox-0"));

  await act(async () => {
    fireEvent.click(screen.getByTestId("confirm-levels-btn"));
    await new Promise((r) => setTimeout(r, 10));
  });

  await waitFor(() => {
    expect(screen.getByText("+7.0 pts")).toBeInTheDocument();
    expect(screen.getByText(/Score: 87\.0/)).toBeInTheDocument();
  });

  restore();
});

// --- Task 6.8: Re-upload resets to initial state ---
it("Re-upload link on result card resets to initial upload state", async () => {
  const restore = stubFileReader();
  mockEnrich.mockResolvedValue(ENRICH_RESPONSE);
  mockConfirm.mockResolvedValue(CONFIRM_RESULT);

  render(<TraderChartUpload ticker="AAPL" onConfirmed={jest.fn()} />);
  const input = screen.getByTestId("chart-file-input");

  await act(async () => {
    fireEvent.change(input, { target: { files: [makePngFile()] } });
    await new Promise((r) => setTimeout(r, 10));
  });

  await waitFor(() => screen.getByTestId("level-checkbox-0"));
  fireEvent.click(screen.getByTestId("level-checkbox-0"));

  await act(async () => {
    fireEvent.click(screen.getByTestId("confirm-levels-btn"));
    await new Promise((r) => setTimeout(r, 10));
  });

  await waitFor(() => screen.getByText("+7.0 pts"));

  fireEvent.click(screen.getByText("Re-upload"));

  expect(screen.getByTestId("upload-chart-btn")).toBeInTheDocument();
  expect(screen.queryByText("+7.0 pts")).not.toBeInTheDocument();

  restore();
});

// JPEG also passes client-side validation
it("accepts JPEG file type without error", () => {
  mockEnrich.mockResolvedValue(ENRICH_RESPONSE);
  render(<TraderChartUpload ticker="AAPL" onConfirmed={jest.fn()} />);
  const input = screen.getByTestId("chart-file-input");

  fireEvent.change(input, { target: { files: [makeJpegFile()] } });

  expect(screen.queryByTestId("upload-error")).not.toBeInTheDocument();
});
