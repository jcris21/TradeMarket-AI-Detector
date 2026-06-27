import { test, expect } from "@playwright/test";

/**
 * E2E tests for Sprint 5 Opportunities Panel features (US-401–404).
 *
 * These tests run against the full Docker stack with LLM_MOCK=true.
 * They seed a completed analysis run via the API before asserting UI state.
 */

test.describe("US-401: Top-N pagination", () => {
  test("8.8 — /api/analysis/latest includes top_n and top_5 alias equals top_n (US-401)", async ({
    request,
  }) => {
    const resp = await request.get("/api/analysis/latest");
    expect(resp.ok()).toBeTruthy();

    const body = await resp.json();

    // top_n field must be present
    expect(body).toHaveProperty("top_n");
    expect(Array.isArray(body.top_n)).toBe(true);

    // If results exist, top_5 alias must equal top_n
    if (body.top_n.length > 0) {
      expect(body).toHaveProperty("top_5");
      expect(body.top_5.length).toBe(body.top_n.length);
      const topNTickers = body.top_n.map((r: { ticker: string }) => r.ticker).sort();
      const top5Tickers = body.top_5.map((r: { ticker: string }) => r.ticker).sort();
      expect(top5Tickers).toEqual(topNTickers);
    }

    // total_analyzed field must be present and be a non-negative number
    expect(body).toHaveProperty("total_analyzed");
    expect(typeof body.total_analyzed).toBe("number");
    expect(body.total_analyzed).toBeGreaterThanOrEqual(0);
  });

  test("8.9 — pagination controls hidden when ≤10 signals; visible when >10", async ({
    page,
    request,
  }) => {
    await page.goto("/");

    // Wait for the opportunities panel to appear
    const panel = page.locator('[aria-label="Top Opportunities"], [data-testid="opportunities-panel"]').first();
    const panelFallback = page.getByText(/Top Opportunities|Analizar/).first();
    await expect(panelFallback).toBeVisible({ timeout: 20_000 });

    const resp = await request.get("/api/analysis/latest");
    const body = await resp.json();
    const signalCount = Array.isArray(body.top_n) ? body.top_n.length : 0;

    if (signalCount <= 10) {
      // Pagination controls should NOT be visible when there are 10 or fewer signals
      const prevBtn = page.getByRole("button", { name: /prev/i });
      const nextBtn = page.getByRole("button", { name: /next/i });
      await expect(prevBtn).not.toBeVisible();
      await expect(nextBtn).not.toBeVisible();
    } else {
      // Pagination controls SHOULD be visible
      const prevBtn = page.getByRole("button", { name: /prev/i });
      const nextBtn = page.getByRole("button", { name: /next/i });
      await expect(prevBtn.or(nextBtn)).toBeVisible({ timeout: 10_000 });

      // Page 1: Prev is disabled, Next is enabled
      await expect(prevBtn).toBeDisabled();
      await expect(nextBtn).toBeEnabled();

      // Navigate to next page
      await nextBtn.click();

      // After navigating, Prev should be enabled
      await expect(prevBtn).toBeEnabled();
    }
  });
});

test.describe("US-402: Collapsible panel", () => {
  test("8.10 — panel collapse state persists across page reload via localStorage", async ({
    page,
    context,
  }) => {
    await page.goto("/");

    // Wait for the opportunities panel heading to appear
    const heading = page.getByText(/Top Opportunities/i).first();
    await expect(heading).toBeVisible({ timeout: 20_000 });

    // Verify panel is expanded by default (localStorage key absent → expanded)
    const initialCollapsed = await page.evaluate(() =>
      localStorage.getItem("finally_top_opps_collapsed")
    );
    // Default: key absent or "false"
    expect(["false", null]).toContain(initialCollapsed);

    // Click the header to collapse
    await heading.click();

    // Confirm localStorage is updated to "true"
    await expect(async () => {
      const val = await page.evaluate(() =>
        localStorage.getItem("finally_top_opps_collapsed")
      );
      expect(val).toBe("true");
    }).toPass({ timeout: 3_000 });

    // Reload the page
    await page.reload();
    await expect(page.getByText(/Top Opportunities/i).first()).toBeVisible({ timeout: 20_000 });

    // After reload, localStorage should still say "true" (collapsed)
    const afterReload = await page.evaluate(() =>
      localStorage.getItem("finally_top_opps_collapsed")
    );
    expect(afterReload).toBe("true");

    // Collapse body should have maxHeight: 0px (content hidden)
    const bodyDiv = page.locator(".overflow-hidden.transition-all").first();
    const maxHeight = await bodyDiv.evaluate((el) =>
      (el as HTMLElement).style.maxHeight
    );
    expect(maxHeight).toBe("0px");

    // Click to expand again (cleanup)
    await (page.getByText(/Top Opportunities/i).first()).click();
    await expect(async () => {
      const val = await page.evaluate(() =>
        localStorage.getItem("finally_top_opps_collapsed")
      );
      expect(val).toBe("false");
    }).toPass({ timeout: 3_000 });
  });
});
