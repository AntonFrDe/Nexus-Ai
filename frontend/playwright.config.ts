import os from "node:os";
import path from "node:path";
import fs from "node:fs";

import { defineConfig } from "@playwright/test";

// A throwaway data directory: E2E runs must never touch the user's real workspaces.
const dataDir = fs.mkdtempSync(path.join(os.tmpdir(), "nexus-e2e-"));
const uv = path.join(os.homedir(), ".local/bin/uv");

export default defineConfig({
  testDir: "e2e",
  fullyParallel: false,
  workers: 1,
  use: { baseURL: "http://localhost:3100", viewport: { width: 1440, height: 900 } },
  webServer: [
    { command: "node e2e/fake-provider.mjs", url: "http://127.0.0.1:11999/api/tags" },
    {
      command: `${uv} run nexus-api`,
      cwd: "../backend",
      url: "http://127.0.0.1:8100/api/health",
      env: { NEXUS_DATA_DIR: dataDir, NEXUS_PORT: "8100", NEXUS_SECRET_BACKEND: "file" },
    },
    {
      command: "npm run dev -- --port 3100",
      url: "http://localhost:3100",
      env: { NEXUS_API_URL: "http://127.0.0.1:8100", NEXT_DIST_DIR: ".next-e2e", NEXUS_DATA_DIR: dataDir },
      timeout: 120_000,
    },
  ],
});
