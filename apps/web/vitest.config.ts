import { configDefaults, defineConfig } from "vitest/config";
import os from "node:os";
import path from "node:path";

export default defineConfig({
  test: {
    environment: "jsdom",
    globals: true,
    // Playwright journeys under e2e/ and e2e-live/ run with Playwright, not vitest.
    exclude: [...configDefaults.exclude, "e2e/**", "e2e-live/**"],
    // Node 26 exposes an experimental localStorage that throws unless it has a backing file;
    // jsdom's own storage is shadowed by it in forked workers.
    poolOptions: { forks: { execArgv: ["--localstorage-file=" + path.join(os.tmpdir(), "campus247-vitest-localstorage.db")] } },
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
