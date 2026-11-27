import "@testing-library/jest-dom/vitest";
import { act, configure, getConfig } from "@testing-library/react";
// The default 1000 ms wait for findBy*/waitFor is too short for a loaded CI runner: several async tests failed there at random
// (and passed on re-run) although they pass locally. A longer ceiling does not slow passing tests; it only stops false failures.
// findBy*/waitFor can return after React has painted but before it has run the passive effects that attach listeners and
// subscriptions. A test that acts at once (types, fires "focus") then talks to a component that is not listening yet and
// waits forever for the result. A person cannot act in that gap, so every async query ends by flushing the effects.
const { asyncWrapper } = getConfig();
configure({
  asyncUtilTimeout: 5000,
  asyncWrapper: async (callback) => {
    const result = await asyncWrapper(callback);
    await act(async () => {});
    return result;
  },
});
// jsdom has no layout engine; resize notifications are exercised separately.
if (typeof globalThis.ResizeObserver === "undefined") {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}
