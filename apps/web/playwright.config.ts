import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 30_000,
  use: { baseURL: "http://127.0.0.1:5173", trace: "retain-on-failure" },
  webServer: [
    {
      command:
        "uv run --project ../.. uvicorn zupulint.api.app:app --host 127.0.0.1 --port 8000",
      cwd: "../..",
      url: "http://127.0.0.1:8000/health",
      reuseExistingServer: true,
    },
    {
      command: "pnpm dev --host 127.0.0.1",
      cwd: ".",
      url: "http://127.0.0.1:5173",
      reuseExistingServer: true,
    },
  ],
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
