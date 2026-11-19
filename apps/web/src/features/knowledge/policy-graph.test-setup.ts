if (typeof window !== "undefined") {
  const { JSDOM } = require("jsdom");
  const browser = new JSDOM("", { url: "http://localhost" });
  const storage = browser.window.localStorage;
  Object.defineProperty(globalThis, "localStorage", {
    value: storage, configurable: true, writable: true,
  });
  Object.defineProperty(window, "localStorage", { value: storage, configurable: true });
}
