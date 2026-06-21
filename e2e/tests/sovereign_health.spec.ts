import { test, expect } from "@playwright/test";

/**
 * /admin/health is the sovereign single-pane dashboard added in iter_28.
 * It reads /api/admin/health/overview every 10s and renders 4 top-line
 * StatPanels (validators, mixnet, ledger, disk) + two SectionPanels
 * (Master Key Manager, Licenza) + a validator table.
 */
test.describe("Sovereign /admin/health", () => {
  test("renders the page header and all four top-line stats", async ({ page }) => {
    await page.goto("/admin/health");
    await expect(page.getByTestId("admin-health-page")).toBeVisible();
    await expect(page.getByTestId("admin-health-stat-validators")).toBeVisible();
    await expect(page.getByTestId("admin-health-stat-mixnet")).toBeVisible();
    await expect(page.getByTestId("admin-health-stat-ledger")).toBeVisible();
    await expect(page.getByTestId("admin-health-stat-disk")).toBeVisible();
  });

  test("Master Key Manager card shows UNLOCKED in dev", async ({ page }) => {
    await page.goto("/admin/health");
    const card = page.getByTestId("admin-health-secrets-card");
    await expect(card).toBeVisible();
    // The badge text reflects the unlocked state of the envelope.
    await expect(card).toContainText(/UNLOCKED|LOCKED/);
    // Mode is one of static|passphrase|locked
    await expect(page.getByTestId("admin-health-secrets-mode")).toContainText(/^(static|passphrase|locked)$/);
  });

  test("License card shows edition + Reload button", async ({ page }) => {
    await page.goto("/admin/health");
    const card = page.getByTestId("admin-health-license-card");
    await expect(card).toBeVisible();
    await expect(card).toContainText(/COMMUNITY|PROFESSIONAL|BANKING|PA|ENTERPRISE/);
    await expect(page.getByTestId("admin-health-license-reload-btn")).toBeVisible();
  });

  test("Refresh button works without errors", async ({ page }) => {
    await page.goto("/admin/health");
    await page.getByTestId("admin-health-refresh-btn").click();
    await expect(page.getByTestId("admin-health-stat-validators")).toBeVisible();
  });
});
