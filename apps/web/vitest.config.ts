import { configDefaults, defineConfig } from "vitest/config";
import path from "node:path";

export default defineConfig({
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    maxWorkers: 4,
    minWorkers: 1,
    // Playwright journeys under e2e/ and e2e-live/ run with Playwright, not vitest.
    exclude: [...configDefaults.exclude, "e2e/**", "e2e-live/**"],
    // Use jsdom's isolated storage instead of Node's shared on-disk storage.
    poolOptions: { forks: { execArgv: ["--no-experimental-webstorage"] } },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  esbuild: {
    jsx: "automatic",
  },
});
