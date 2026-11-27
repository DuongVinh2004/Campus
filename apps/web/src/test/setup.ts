import "@testing-library/jest-dom/vitest";
import { configure } from "@testing-library/react";
// The default 1000 ms wait for findBy*/waitFor is too short for a loaded CI runner: several async tests failed there at random
// (and passed on re-run) although they pass locally. A longer ceiling does not slow passing tests; it only stops false failures.
configure({ asyncUtilTimeout: 5000 });
// jsdom has no layout engine; resize notifications are exercised separately.
if (typeof globalThis.ResizeObserver === "undefined") {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}
