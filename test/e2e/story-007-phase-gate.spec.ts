import { test, expect } from "@playwright/test";

// ── STORY-007: Statistical Validity Phase Gate ────────────────────────────────
//
// Tests the 4-phase model added to GET /api/analysis/performance:
//   Phase 0 — Calibration  (<30 conclusive signals)
//   Phase 1 — Pilot        (30–99)
//   Phase 2 — Evaluation   (100–299)
//   Phase 3 — Confident    (≥300)
//
// API tests use the `request` fixture (no browser spawn overhead).
// UI tests use the `page` fixture and auto-skip when the frontend is not served.

// ── API: phase field ──────────────────────────────────────────────────────────

test.describe("GET /api/analysis/performance — story-007 phase field", () => {
  test("response includes `phase` field as an integer 0–3", async ({
    request,
  }) => {
    const resp = await request.get("/api/analysis/performance");
    expect(resp.status()).toBe(200);

    const data = await resp.json();
    expect(data).toHaveProperty("phase");
    expect(typeof data.phase).toBe("number");
    expect(Number.isInteger(data.phase)).toBe(true);
    expect(data.phase).toBeGreaterThanOrEqual(0);
    expect(data.phase).toBeLessThanOrEqual(3);
  });

  test("response includes `phase_banner` as a non-empty string", async ({
    request,
  }) => {
    const resp = await request.get("/api/analysis/performance");
    expect(resp.status()).toBe(200);

    const data = await resp.json();
    expect(data).toHaveProperty("phase_banner");
    expect(typeof data.phase_banner).toBe("string");
    expect(data.phase_banner.length).toBeGreaterThan(0);
  });

  test("phase_banner contains 'Calibration' when phase === 0", async ({
    request,
  }) => {
    const resp = await request.get("/api/analysis/performance");
    const data = await resp.json();

    if (data.phase === 0) {
      expect(data.phase_banner).toContain("Calibration");
    }
  });

  test("phase_banner contains 'Phase 0:' substring when phase === 0", async ({
    request,
  }) => {
    const resp = await request.get("/api/analysis/performance");
    const data = await resp.json();

    if (data.phase === 0) {
      expect(data.phase_banner).toContain("Phase 0:");
    }
  });

  test("backward-compat: phase_gate_active === (phase === 0)", async ({
    request,
  }) => {
    const resp = await request.get("/api/analysis/performance");
    const data = await resp.json();

    // phase_gate_active must equal true if and only if phase is 0
    expect(data.phase_gate_active).toBe(data.phase === 0);
  });

  test("calibration_count range is consistent with phase", async ({
    request,
  }) => {
    const resp = await request.get("/api/analysis/performance");
    const data = await resp.json();

    const n: number = data.calibration_count;
    const phase: number = data.phase;

    if (phase === 0) {
      expect(n).toBeGreaterThanOrEqual(0);
      expect(n).toBeLessThan(30);
    } else if (phase === 1) {
      expect(n).toBeGreaterThanOrEqual(30);
      expect(n).toBeLessThan(100);
    } else if (phase === 2) {
      expect(n).toBeGreaterThanOrEqual(100);
      expect(n).toBeLessThan(300);
    } else if (phase === 3) {
      expect(n).toBeGreaterThanOrEqual(300);
    }
  });
});

// ── API: phase_banner label content per phase ─────────────────────────────────

test.describe("GET /api/analysis/performance — phase_banner content", () => {
  test("phase_banner includes correct label keyword for the current phase", async ({
    request,
  }) => {
    const resp = await request.get("/api/analysis/performance");
    const data = await resp.json();

    const labelByPhase: Record<number, string> = {
      0: "Calibration",
      1: "Pilot",
      2: "Evaluation",
      3: "Confident",
    };

    const expected = labelByPhase[data.phase as number];
    if (expected !== undefined) {
      expect(data.phase_banner).toContain(expected);
    }
  });

  test("phase_banner includes signal count and phase number", async ({
    request,
  }) => {
    const resp = await request.get("/api/analysis/performance");
    const data = await resp.json();

    // Banner must always mention the signal count as a digit
    expect(data.phase_banner).toMatch(/\d+/);
    // Banner must mention the phase number
    expect(data.phase_banner).toContain(`Phase ${data.phase}:`);
  });

  test("phase_banner includes 'signals' word", async ({ request }) => {
    const resp = await request.get("/api/analysis/performance");
    const data = await resp.json();

    expect(data.phase_banner.toLowerCase()).toContain("signals");
  });
});

// ── API: Story-004 regression — existing fields still present ─────────────────

test.describe("GET /api/analysis/performance — story-004 regression (007)", () => {
  test("story-004 status fields still present in response", async ({
    request,
  }) => {
    const resp = await request.get("/api/analysis/performance");
    expect(resp.status()).toBe(200);

    const data = await resp.json();
    const story004Fields = [
      "phase_gate_active",
      "calibration_count",
      "realized_rr",
      "hr_status",
      "pf_status",
      "rr_status",
      "below_breakeven",
    ];
    for (const field of story004Fields) {
      expect(data).toHaveProperty(field);
    }
  });

  test("metric fields are null when phase === 0 (gate active)", async ({
    request,
  }) => {
    const resp = await request.get("/api/analysis/performance");
    const data = await resp.json();

    if (data.phase === 0) {
      expect(data.hit_ratio).toBeNull();
      expect(data.profit_factor).toBeNull();
      expect(data.realized_rr).toBeNull();
      expect(data.hr_status).toBeNull();
      expect(data.pf_status).toBeNull();
      expect(data.rr_status).toBeNull();
    }
  });
});

// ── UI: PerformanceSummaryPanel — phase gate rendering ────────────────────────
//
// Requires the full app (frontend + backend) at baseURL.
// Auto-skips when the frontend is not served.

test.describe("PerformanceSummaryPanel — story-007 phase banner", () => {
  test.beforeEach(async ({ page }) => {
    try {
      await page.goto("/");
    } catch {
      test.skip(true, "Frontend not served at baseURL — start Docker container or Next.js dev server");
      return;
    }
    const title = await page.title();
    test.skip(
      !title.toLowerCase().includes("finally"),
      "Frontend not served at baseURL — start Docker container or Next.js dev server"
    );
  });

  test("phase_banner text from API is visible on the page", async ({ page }) => {
    // Fetch the banner text from the API directly
    const resp = await page.request.get("/api/analysis/performance");
    const data = await resp.json();
    const banner: string = data.phase_banner;

    // Wait for the panel landmark to appear
    await expect(page.getByText("TOP OPORTUNIDADES")).toBeVisible({
      timeout: 15_000,
    });

    // The banner text (or a meaningful substring) must be visible in the UI
    // We use a substring because the full emoji+text may be split across nodes
    const bannerSubstring = banner.replace(/^📊\s*/, "").split("·")[0].trim();
    await expect(
      page.getByText(new RegExp(bannerSubstring.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "i"))
    ).toBeVisible({ timeout: 10_000 });
  });

  test("text matching /Phase 0: Calibration/i is visible when phase === 0", async ({
    page,
  }) => {
    const resp = await page.request.get("/api/analysis/performance");
    const data = await resp.json();

    if (data.phase !== 0) {
      test.skip(true, "phase is not 0 — skipping Phase 0 specific UI check");
    }

    await expect(page.getByText("TOP OPORTUNIDADES")).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByText(/Phase 0.*Calibration/i)).toBeVisible({
      timeout: 10_000,
    });
  });

  test("Phase 0 banner contains N/30 signals substring", async ({ page }) => {
    const resp = await page.request.get("/api/analysis/performance");
    const data = await resp.json();

    if (data.phase !== 0) {
      test.skip(true, "phase is not 0 — skipping N/30 signals check");
    }

    await expect(page.getByText("TOP OPORTUNIDADES")).toBeVisible({
      timeout: 15_000,
    });

    // The banner should include "{n}/30 signals" — N comes from calibration_count
    await expect(page.getByText(/\d+\/30 signals/i)).toBeVisible({
      timeout: 10_000,
    });
  });

  test("no Pilot / Evaluation / Confident label visible when phase === 0", async ({
    page,
  }) => {
    const resp = await page.request.get("/api/analysis/performance");
    const data = await resp.json();

    if (data.phase !== 0) {
      test.skip(true, "phase is not 0 — skipping absent-label check");
    }

    await expect(page.getByText("TOP OPORTUNIDADES")).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByText(/Phase 0.*Calibration/i)).toBeVisible({
      timeout: 10_000,
    });

    // Labels from later phases must not be visible during calibration
    await expect(page.getByText(/\bPilot\b/i)).toHaveCount(0);
    await expect(page.getByText(/\bEvaluation\b/i)).toHaveCount(0);
    await expect(page.getByText(/\bConfident\b/i)).toHaveCount(0);
  });

  test("metric visibility is consistent with phase_gate_active and phase field", async ({
    page,
  }) => {
    const resp = await page.request.get("/api/analysis/performance");
    const data = await resp.json();

    await expect(page.getByText("TOP OPORTUNIDADES")).toBeVisible({
      timeout: 15_000,
    });

    if (data.phase_gate_active) {
      // phase_gate_active means phase === 0; metrics must be hidden
      expect(data.phase).toBe(0);
      await expect(page.getByText(/Hit Ratio/i)).toHaveCount(0);
      await expect(page.getByText(/Profit Factor/i)).toHaveCount(0);
      await expect(page.getByText(/Realized R\/R/i)).toHaveCount(0);
    } else {
      // phase >= 1; metrics panel should be visible
      expect(data.phase).toBeGreaterThanOrEqual(1);
      await expect(page.getByText(/Hit Ratio/i)).toBeVisible({
        timeout: 10_000,
      });
    }
  });
});

// ── UI: Phase 1+ metric panel renders when phase >= 1 ────────────────────────

test.describe("PerformanceSummaryPanel — phase 1+ metric rendering", () => {
  test.beforeEach(async ({ page }) => {
    try {
      await page.goto("/");
    } catch {
      test.skip(true, "Frontend not served at baseURL — start Docker container or Next.js dev server");
      return;
    }
    const title = await page.title();
    test.skip(
      !title.toLowerCase().includes("finally"),
      "Frontend not served at baseURL — start Docker container or Next.js dev server"
    );
  });

  test("when phase >= 1, phase header shows correct phase number and label", async ({
    page,
  }) => {
    const resp = await page.request.get("/api/analysis/performance");
    const data = await resp.json();

    if (data.phase < 1) {
      test.skip(true, "phase is 0 — skipping phase 1+ header check");
    }

    await expect(page.getByText("TOP OPORTUNIDADES")).toBeVisible({
      timeout: 15_000,
    });

    const labelByPhase: Record<number, string> = {
      1: "Pilot",
      2: "Evaluation",
      3: "Confident",
    };
    const label = labelByPhase[data.phase as number] ?? "";
    if (label) {
      await expect(
        page.getByText(new RegExp(`Phase ${data.phase}.*${label}`, "i"))
      ).toBeVisible({ timeout: 10_000 });
    }
  });

  test("when phase >= 1, metric rows (Hit Ratio, Profit Factor, Realized R/R) are present", async ({
    page,
  }) => {
    const resp = await page.request.get("/api/analysis/performance");
    const data = await resp.json();

    if (data.phase < 1) {
      test.skip(true, "phase is 0 — metrics are intentionally hidden during calibration");
    }

    await expect(page.getByText("TOP OPORTUNIDADES")).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByText(/Hit Ratio/i)).toBeVisible({
      timeout: 10_000,
    });
    await expect(page.getByText(/Profit Factor/i)).toBeVisible({
      timeout: 10_000,
    });
    await expect(page.getByText(/Realized R\/R/i)).toBeVisible({
      timeout: 10_000,
    });
  });
});
