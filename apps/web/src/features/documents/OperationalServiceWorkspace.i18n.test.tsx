import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { LanguageProvider } from "../../lib/i18n";
import { OperationalServiceWorkspace } from "./OperationalServiceWorkspace";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }), useSearchParams: () => new URLSearchParams(), usePathname: () => "/services" }));

beforeEach(() => {
  document.cookie = "lang=en; path=/";
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ code: "AUTHENTICATION_REQUIRED" }), { status: 401, headers: { "Content-Type": "application/json" } })));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); document.cookie = "lang=; path=/; max-age=0"; });

describe("service workspace in English", () => {
  it("shows the English heading, the notice about what the page does and the sign-in link", async () => {
    render(<LanguageProvider><OperationalServiceWorkspace /></LanguageProvider>);
    expect(await screen.findByRole("heading", { name: "Academic services" })).toBeInTheDocument();
    expect(screen.getByText(/You can prepare, preview and save a private draft here/)).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "Sign in" })).toBeInTheDocument();
  });
});
