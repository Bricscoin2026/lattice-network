import { defineConfig, devices } from "@playwright/test";

/**
 * Lattice Network — Playwright config.
 *
 * Target URL precedence:
 *   1. PLAYWRIGHT_BASE_URL env var (CI / docker-compose)
 *   2. fallback to the dev preview baked into frontend/.env
 *
 * The dev preview is read at config load time from REACT_APP_BACKEND_URL
 * so the same suite drives the local container and the deployed instance.
 */
import * as fs from "node:fs";
import * as path from "node:path";

function readFrontendBaseUrl(): string {
  const envFile = path.resolve(__dirname, "..", "frontend", ".env");
  try {
    const raw = fs.readFileSync(envFile, "utf-8");
    const match = raw.match(/^REACT_APP_BACKEND_URL\s*=\s*(.+)$/m);
    if (match) return match[1].trim().replace(/^"|"$/g, "");
  } catch {
    /* ignored */
  }
  return "http://localhost:3000";
}

const baseURL = process.env.PLAYWRIGHT_BASE_URL || readFrontendBaseUrl();

export default defineConfig({
  testDir: "./tests",
  timeout: 60_000,
  expect: { timeout: 8_000 },
  fullyParallel: false,            // sovereign state is shared, run serially
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [
    ["list"],
    ["html", { open: "never", outputFolder: "playwright-report" }],
  ],
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    viewport: { width: 1440, height: 900 },
    extraHTTPHeaders: {
      // Dev-mode role pinning so sovereign endpoints are reachable
      // without a JWT. Match the RBAC defaults documented in PRD.md.
      "X-Lattice-Role": "sovereign",
    },
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
});
