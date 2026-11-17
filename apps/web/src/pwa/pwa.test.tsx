import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import manifest from "../app/manifest";
import OfflinePage from "../app/offline/page";
import { clearPwaCaches, PwaRegister } from "../components/PwaRegister";
import { InstallPrompt, isIos } from "../components/InstallPrompt";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("manifest", () => {
  it("makes the app installable: name, standalone, start inside the scope, three icons including a maskable one", () => {
    const m = manifest();
    expect(m.name).toBe("Campus 24/7");
    expect(m.display).toBe("standalone");
    expect(m.lang).toBe("vi");
    expect(m.start_url!.startsWith(m.scope!)).toBe(true);
    const icons = m.icons!;
    expect(icons.map((i) => i.sizes).sort()).toEqual(["192x192", "512x512", "512x512"]);
    expect(icons.some((i) => i.purpose === "maskable")).toBe(true);
    expect(icons.every((i) => i.type === "image/png" && i.src.startsWith("/icons/"))).toBe(true);
  });

  it("does not present itself as an official school service", () => {
    expect(manifest().description).toContain("không phải dịch vụ chính thức");
  });
});

describe("offline page", () => {
  it("is static, says there is no connection and offers a retry", () => {
    render(<OfflinePage />);
    expect(screen.getByRole("heading").textContent).toContain("ngoại tuyến");
    expect(screen.getByRole("link", { name: "Thử lại" }).getAttribute("href")).toBe("/");
  });
});

describe("PwaRegister", () => {
  const register = vi.fn();
  beforeEach(() => {
    register.mockReset();
    register.mockResolvedValue({}); // restoreAllMocks in afterEach also clears this implementation, so it is set again for every test
    vi.stubGlobal("navigator", { ...navigator, serviceWorker: { register } });
  });

  it("registers /sw.js with scope / in a secure context", () => {
    vi.stubGlobal("isSecureContext", true);
    render(<PwaRegister />);
    expect(register).toHaveBeenCalledWith("/sw.js", { scope: "/" });
  });

  it("does nothing when the context is not secure", () => {
    vi.stubGlobal("isSecureContext", false);
    render(<PwaRegister />);
    expect(register).not.toHaveBeenCalled();
  });

  it("survives a failed registration", async () => {
    vi.stubGlobal("isSecureContext", true);
    register.mockRejectedValueOnce(new Error("blocked"));
    render(<PwaRegister />);
    await act(async () => undefined);
  });

  it("asks the active worker to clear its caches on sign-out", async () => {
    const postMessage = vi.fn();
    vi.stubGlobal("navigator", { serviceWorker: { getRegistration: () => Promise.resolve({ active: { postMessage } }) } });
    clearPwaCaches();
    await act(async () => undefined);
    expect(postMessage).toHaveBeenCalledWith({ type: "campus247:clear-caches" });
  });

  it("clearing without a service worker is a no-op", () => {
    vi.stubGlobal("navigator", {});
    expect(() => clearPwaCaches()).not.toThrow();
  });
});

describe("InstallPrompt", () => {
  it("offers an install button after the browser fires beforeinstallprompt and calls the browser's prompt", async () => {
    render(<InstallPrompt />);
    const prompt = vi.fn().mockResolvedValue(undefined);
    const event = Object.assign(new Event("beforeinstallprompt", { cancelable: true }), { prompt, userChoice: Promise.resolve({ outcome: "accepted" }) });
    act(() => void window.dispatchEvent(event));
    expect(event.defaultPrevented).toBe(true);
    await act(async () => void fireEvent.click(await screen.findByRole("button", { name: "Cài ứng dụng Campus 24/7" })));
    expect(prompt).toHaveBeenCalledOnce();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("shows nothing by default and nothing once the app is installed", () => {
    const { container } = render(<InstallPrompt />);
    expect(container.innerHTML).toBe("");
    act(() => void window.dispatchEvent(new Event("appinstalled")));
    expect(container.innerHTML).toBe("");
  });

  it("explains how to install on iPhone, which has no prompt", () => {
    vi.stubGlobal("navigator", { userAgent: "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)" });
    render(<InstallPrompt />);
    expect(screen.getByTestId("ios-install-hint").textContent).toContain("Chia sẻ");
  });

  it("recognizes iOS devices only", () => {
    expect(isIos("Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X)")).toBe(true);
    expect(isIos("Mozilla/5.0 (Linux; Android 14)")).toBe(false);
  });
});
