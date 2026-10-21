import { defineConfig, devices } from "@playwright/test";

/**
 * E2E: настоящий бэкенд на отдельной базе *_e2e и dev-сервер Vite.
 * Локально база — в том же контейнере Postgres (порт 5110), в CI — сервис.
 */
const DATABASE_URL =
  process.env.E2E_DATABASE_URL ?? "postgresql://postgres:postgres@localhost:5110/wood_commerce_e2e";
const PYTHON = process.env.E2E_PYTHON ?? ".venv/bin/python";
const API_PORT = 8010;
const WEB_PORT = 5180;

export default defineConfig({
  testDir: "e2e",
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: `http://127.0.0.1:${WEB_PORT}`,
    locale: "ru-RU",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: `${PYTHON} seed_e2e.py && ${PYTHON} -m uvicorn app.main:app --port ${API_PORT}`,
      cwd: "../backend",
      url: `http://127.0.0.1:${API_PORT}/api/v1/health`,
      env: { DATABASE_URL, SECRET_KEY: "e2e-secret", TELEGRAM_BOT_TOKEN: "" },
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: `npm run dev -- --host 127.0.0.1 --port ${WEB_PORT} --strictPort`,
      url: `http://127.0.0.1:${WEB_PORT}`,
      env: { API_TARGET: `http://127.0.0.1:${API_PORT}` },
      reuseExistingServer: false,
    },
  ],
});
