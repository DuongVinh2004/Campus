import { defineConfig, mergeConfig } from "vitest/config";
import base from "./vitest.config";

// Keep the existing tests intact. Node 26's experimental global Web Storage
// shadows jsdom's browser storage unless the harness binds it explicitly.
export default mergeConfig(base, defineConfig({
  test: { setupFiles: ["./src/features/knowledge/policy-graph.test-setup.ts"] },
}));
