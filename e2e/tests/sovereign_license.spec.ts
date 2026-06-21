import { test, expect } from "@playwright/test";

/**
 * Backend-via-Playwright tests for the ML-DSA-65 license endpoint.
 * Playwright's `request` fixture inherits `baseURL` + `extraHTTPHeaders`
 * (so X-Lattice-Role: sovereign is automatically attached).
 */
test.describe("License system", () => {
  test("status endpoint returns license metadata", async ({ request }) => {
    const r = await request.get("/api/admin/license/status");
    expect(r.status()).toBe(200);
    const body = await r.json();
    expect(body).toHaveProperty("edition");
    expect(body).toHaveProperty("vendor_pubkey_installed");
    expect(["community", "professional", "banking", "pa", "enterprise"]).toContain(body.edition);
  });

  test("forged signature is rejected with 403", async ({ request }) => {
    // 3309 bytes of zero hex — wrong signature, right length.
    const sigHex = "00".repeat(3309);
    const payload = {
      license: {
        license_id: "lic-attack",
        edition: "enterprise",
        tenant_name: "Attacker SpA",
        max_tenants: 1,
        max_users: 1,
        features: [],
        valid_from: "2026-01-01T00:00:00Z",
        valid_until: "2027-01-01T00:00:00Z",
        issued_to_fingerprint: "deadbeef",
        signature_hex: sigHex,
      },
    };
    const r = await request.post("/api/admin/license/install", { data: payload });
    expect(r.status()).toBe(403);
    const body = await r.json();
    expect(body.detail).toMatch(/signature/i);
  });

  test("short signature is rejected with 403", async ({ request }) => {
    const payload = {
      license: {
        license_id: "lic-attack-short",
        edition: "enterprise",
        tenant_name: "Attacker",
        max_tenants: 1,
        max_users: 1,
        features: [],
        valid_from: "2026-01-01T00:00:00Z",
        valid_until: "2027-01-01T00:00:00Z",
        issued_to_fingerprint: "deadbeef",
        signature_hex: "deadbeef",
      },
    };
    const r = await request.post("/api/admin/license/install", { data: payload });
    expect(r.status()).toBe(403);
  });

  test("license file reload preserves edition", async ({ request }) => {
    const before = await (await request.get("/api/admin/license/status")).json();
    const r = await request.post("/api/admin/license/reload");
    expect(r.status()).toBe(200);
    const body = await r.json();
    expect(body.ok).toBe(true);
    expect(body.status.edition).toBe(before.edition);
  });
});
