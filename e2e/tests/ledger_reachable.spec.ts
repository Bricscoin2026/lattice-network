import { test, expect } from "@playwright/test";

/** Smoke tests for the core read-only endpoints used by every dashboard. */
test.describe("Core read endpoints", () => {
  const endpoints = [
    "/api/qbft/status",
    "/api/mixnet/status",
    "/api/ledger/stats",
    "/api/certify/stats",
    "/api/config/runtime",
    "/api/admin/health/overview",
  ];

  for (const ep of endpoints) {
    test(`${ep} returns 200`, async ({ request }) => {
      const r = await request.get(ep);
      expect(r.status(), `expected 200 from ${ep}`).toBe(200);
      const body = await r.json();
      expect(body).toBeTruthy();
    });
  }

  test("/api/admin/health/overview aggregates the expected sections", async ({ request }) => {
    const r = await request.get("/api/admin/health/overview");
    const body = await r.json();
    for (const key of ["timestamp", "secrets", "license", "validators", "mixnet", "chain", "disk", "alerts"]) {
      expect(body, `missing top-level key: ${key}`).toHaveProperty(key);
    }
  });
});
