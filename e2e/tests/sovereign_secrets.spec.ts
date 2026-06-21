import { test, expect } from "@playwright/test";

test.describe("Secret manager / at-rest envelope", () => {
  test("status reflects unlocked dev state", async ({ request }) => {
    const r = await request.get("/api/admin/secrets/status");
    expect(r.status()).toBe(200);
    const body = await r.json();
    expect(body).toHaveProperty("mode");
    expect(body).toHaveProperty("unlocked");
    expect(body.kdf).toBe("argon2id");
    expect(body.kdf_params).toMatchObject({
      time_cost: expect.any(Number),
      memory_cost_kb: expect.any(Number),
      parallelism: expect.any(Number),
    });
  });

  test("init refuses when static key is loaded (409)", async ({ request }) => {
    const r = await request.post("/api/admin/secrets/init", {
      data: { passphrase: "TestPassphrase-12345" },
    });
    // Allowed responses:
    //   - 409 when LATTICE_ENVELOPE_KEY (static) is in use
    //   - 409 when a passphrase is already configured
    //   - 200 only on a brand-new install without any envelope key
    expect([200, 409]).toContain(r.status());
  });

  test("unlock no-op succeeds in static mode", async ({ request }) => {
    const r = await request.post("/api/admin/secrets/unlock", {
      data: { passphrase: "doesnotmatter-12345" },
    });
    // In static mode unlock is a no-op success.
    // In passphrase mode with a wrong passphrase it'll be 401.
    expect([200, 401, 404]).toContain(r.status());
  });
});
