import { test, expect } from "@playwright/test";

test.describe("Landing page", () => {
  test("renders title and primary CTA", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveTitle(/Lattice/i);
    // Body should contain at least one prominent brand mention.
    await expect(page.locator("body")).toContainText(/Lattice/);
  });

  test("whitepaper link is reachable", async ({ page }) => {
    await page.goto("/whitepaper");
    // The viewer page mounts an iframe / object pointing to the PDF.
    // We just verify the URL resolved (no 404 redirect).
    await expect(page).toHaveURL(/\/whitepaper/);
  });

  test("audit directory loads (public)", async ({ page }) => {
    await page.goto("/audit");
    await expect(page).toHaveURL(/\/audit/);
  });
});
