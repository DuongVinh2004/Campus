import path from "node:path";
import { defineConfig, mergeConfig } from "vitest/config";
import base from "./vitest.policy-graph.config";

export default mergeConfig(base, defineConfig({
  cacheDir: path.resolve(__dirname, "../../infra/local/unified-ai-20261014-03/vite-cache01"),
}));
