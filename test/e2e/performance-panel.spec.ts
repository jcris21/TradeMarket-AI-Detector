import { test, expect } from "@playwright/test";

// ── API: New fields from story-004 ────────────────────────────────────────────

test.describe("GET /api/analysis/performance — story-004 new fields", () => {
  test("response includes all story-004 fields", async ({ request }) => {
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

  test("phase_gate_active is true and calibration_count is below 30 on a non-production DB", async ({
    request,
  }) => {
    const resp = await request.get("/api/analysis/performance");
    expect(resp.status()).toBe(200);

    const data = await resp.json();
    // Dev/test DB has fewer than 30 conclusive signals → phase gate active
    expect(data.phase_gate_active).toBe(true);
    expect(data.calibration_count).toBeGreaterThanOrEqual(0);
    expect(data.calibration_count).toBeLessThan(30);
  });

  test("metric fields are null when phase gate is active", async ({
    request,
  }) => {
    const resp = await request.get("/api/analysis/performance");
    expect(resp.status()).toBe(200);

    const data = await resp.json();
    if (data.phase_gate_active) {
      expect(data.hit_ratio).toBeNull();
      expect(data.profit_factor).toBeNull();
      expect(data.realized_rr).toBeNull();
      expect(data.hr_status).toBeNull();
      expect(data.pf_status).toBeNull();
      expect(data.rr_status).toBeNull();
    }
  });

  test("below_breakeven is false when phase gate is active", async ({ request }) => {
    const resp = await request.get("/api/analysis/performance");
    const data = await resp.json();

    if (data.phase_gate_active) {
      expect(data.below_breakeven).toBe(false);
    }
  });

  test("calibration_count equals target_hits + stop_hits", async ({
    request,
  }) => {
    const resp = await request.get("/api/analysis/performance");
    const data = await resp.json();

    const conclusive = (data.target_hits ?? 0) + (data.stop_hits ?? 0);
    expect(data.calibration_count).toBe(conclusive);
  });

  test("phase_gate_active type is boolean", async ({ request }) => {
    const resp = await request.get("/api/analysis/performance");
    const data = await resp.json();

    expect(typeof data.phase_gate_active).toBe("boolean");
  });

  test("calibration_count is a non-negative integer", async ({ request }) => {
    const resp = await request.get("/api/analysis/performance");
    const data = await resp.json();

    expect(typeof data.calibration_count).toBe("number");
    expect(Number.isInteger(data.calibration_count)).toBe(true);
    expect(data.calibration_count).toBeGreaterThanOrEqual(0);
  });

  test("status fields are null or one of the allowed string values", async ({
    request,
  }) => {
    const resp = await request.get("/api/analysis/performance");
    const data = await resp.json();

    const allowed = ["green", "red", "neutral", null];
    expect(allowed).toContain(data.hr_status);
    expect(allowed).toContain(data.pf_status);
    expect(allowed).toContain(data.rr_status);
  });

  test("realized_rr is null or a positive finite number", async ({
    request,
  }) => {
    const resp = await request.get("/api/analysis/performance");
    const data = await resp.json();

    if (data.realized_rr !== null) {
      expect(typeof data.realized_rr).toBe("number");
      expect(Number.isFinite(data.realized_rr)).toBe(true);
      expect(data.realized_rr).toBeGreaterThan(0);
    }
  });
});

// ── UI: PerformanceSummaryPanel — calibration state ───────────────────────────
//
// These tests require the full app (frontend + backend) at baseURL.
// Run the Docker container (scripts/start_*.ps1) or the Next.js dev server
// (npm run dev in frontend/) for them to execute.
// They auto-skip when the root URL returns JSON (backend-only mode).

test.describe("PerformanceSummaryPanel — calibration state", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    const title = await page.title();
    test.skip(
      !title.toLowerCase().includes("finally"),
      "Frontend not served at baseURL — start Docker container or Next.js dev server"
    );
  });

  test("Phase 0 Calibration section is visible", async ({ page }) => {
    await expect(page.getByText("TOP OPORTUNIDADES")).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByText(/Phase 0.*Calibration/i)).toBeVisible({
      timeout: 10_000,
    });
  });

  test("calibration count badge shows N/30 signals format", async ({ page }) => {
    await expect(page.getByText("TOP OPORTUNIDADES")).toBeVisible({
      timeout: 15_000,
    });
    // The badge format is "{n}/30 signals" — n depends on seeded data
    await expect(page.getByText(/\d+\/30 signals/i)).toBeVisible({
      timeout: 10_000,
    });
  });

  test("calibration progress bar is rendered with correct width", async ({
    page,
  }) => {
    await expect(page.getByText(/Phase 0.*Calibration/i)).toBeVisible({
      timeout: 15_000,
    });

    const progressFill = page.locator(".bg-accent-yellow.rounded-full").first();
    await expect(progressFill).toBeVisible();

    // Width reflects calibration_count/30 — must be a valid CSS percentage
    const width = await progressFill.evaluate(
      (el) => (el as HTMLElement).style.width
    );
    expect(width).toMatch(/^\d+(\.\d+)?%$/);
    const pct = parseFloat(width);
    expect(pct).toBeGreaterThanOrEqual(0);
    expect(pct).toBeLessThan(100);
  });

  test("metric rows (Hit Ratio, Profit Factor, Realized R/R) are absent during calibration", async ({
    page,
  }) => {
    await expect(page.getByText(/Phase 0.*Calibration/i)).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByText(/Hit Ratio/i)).toHaveCount(0);
    await expect(page.getByText(/Profit Factor/i)).toHaveCount(0);
    await expect(page.getByText(/Realized R\/R/i)).toHaveCount(0);
  });

  test("break-even warning is absent during calibration", async ({ page }) => {
    await expect(page.getByText(/Phase 0.*Calibration/i)).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByText(/below break-even/i)).toHaveCount(0);
  });

  test("Phase 1 Performance / Live Metrics Active badge is absent during calibration", async ({
    page,
  }) => {
    await expect(page.getByText(/Phase 0.*Calibration/i)).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByText(/Live Metrics Active/i)).toHaveCount(0);
  });
});

// ── UI: PerformanceSummaryPanel — placement and regression ────────────────────
//
// Note: the below_breakeven=true scenario (warning banner visible) is not tested
// here because it requires seeding > 30 conclusive signals with HR < 0.25, which
// cannot be done through the public REST API. The scenario is covered by the
// unit tests in frontend/__tests__/PerformanceSummaryPanel.test.tsx.

test.describe("PerformanceSummaryPanel — placement and regression", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    const title = await page.title();
    test.skip(
      !title.toLowerCase().includes("finally"),
      "Frontend not served at baseURL — start Docker container or Next.js dev server"
    );
  });

  test("panel renders below tab bar", async ({ page }) => {
    await expect(page.getByText("TOP OPORTUNIDADES")).toBeVisible({
      timeout: 15_000,
    });

    const activeTab = page.getByRole("button", { name: /oportunidades/i });
    const archiveTab = page.getByRole("button", { name: /archivo/i });
    await expect(activeTab).toBeVisible();
    await expect(archiveTab).toBeVisible();

    const panel = page.getByText(/Phase 0.*Calibration/i);
    await expect(panel).toBeVisible({ timeout: 10_000 });

    const tabBox = await activeTab.boundingBox();
    const panelBox = await panel.boundingBox();
    expect(tabBox).not.toBeNull();
    expect(panelBox).not.toBeNull();
    expect(panelBox!.y).toBeGreaterThanOrEqual(tabBox!.y);
  });

  test("panel remains visible when switching to Archive tab", async ({
    page,
  }) => {
    await expect(page.getByText("TOP OPORTUNIDADES")).toBeVisible({
      timeout: 15_000,
    });
    await page.getByRole("button", { name: /archivo/i }).click();
    await expect(page.getByText(/Phase 0.*Calibration/i)).toBeVisible({
      timeout: 10_000,
    });
  });

  test("no JS errors after panel renders", async ({ page }) => {
    const errors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") errors.push(msg.text());
    });

    await expect(page.getByText("TOP OPORTUNIDADES")).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByText(/Phase 0.*Calibration/i)).toBeVisible({
      timeout: 10_000,
    });

    const critical = errors.filter(
      (e) => !e.includes("favicon") && !e.includes("404")
    );
    expect(critical).toHaveLength(0);
  });

  test("loading skeleton disappears once performance data loads", async ({
    page,
  }) => {
    await expect(page.getByText("TOP OPORTUNIDADES")).toBeVisible({
      timeout: 15_000,
    });
    // Once "Phase 0 — Calibration" is visible the skeleton must be gone
    await expect(page.getByText(/Phase 0.*Calibration/i)).toBeVisible({
      timeout: 10_000,
    });
    // The loading skeleton (animate-pulse) must not coexist with the rendered panel
    const skeleton = page.locator(".animate-pulse").filter({ hasText: /^$/ });
    await expect(skeleton).toHaveCount(0);
  });
});

// ── API: Regression — existing fields still present ──────────────────────────

test.describe("GET /api/analysis/performance — story-004 regression", () => {
  test("original fields (total_signals, target_hits, stop_hits, expired, orphaned_count) still present", async ({
    request,
  }) => {
    const resp = await request.get("/api/analysis/performance");
    expect(resp.status()).toBe(200);

    const data = await resp.json();
    const legacy = [
      "total_signals",
      "target_hits",
      "stop_hits",
      "expired",
      "orphaned_count",
    ];
    for (const field of legacy) {
      expect(data).toHaveProperty(field);
    }
  });

  test("hit_ratio is a number in [0,1] when phase gate is inactive", async ({
    request,
  }) => {
    const resp = await request.get("/api/analysis/performance");
    const data = await resp.json();

    if (!data.phase_gate_active) {
      expect(typeof data.hit_ratio).toBe("number");
      expect(data.hit_ratio).toBeGreaterThanOrEqual(0);
      expect(data.hit_ratio).toBeLessThanOrEqual(1);
    }
  });

  test("profit_factor is null or a finite number ≤ 999 (never raw Infinity)", async ({
    request,
  }) => {
    const resp = await request.get("/api/analysis/performance");
    const data = await resp.json();

    const pf = data.profit_factor;
    expect(pf === null || typeof pf === "number").toBe(true);
    if (typeof pf === "number") {
      expect(Number.isFinite(pf)).toBe(true);
      expect(pf).toBeLessThanOrEqual(999.0);
    }
  });
});
