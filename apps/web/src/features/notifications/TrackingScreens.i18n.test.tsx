import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { LanguageProvider } from "../../lib/i18n";
import { NotificationCenter } from "./NotificationCenter";
import { MemoryCenter } from "../memory/MemoryCenter";

vi.mock("next/link", () => ({ default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => <a href={href} {...rest}>{children}</a> }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/lib/unified-assistant-runtime", () => ({ useOptionalUnifiedAssistant: () => null, useUnifiedAssistant: () => null }));
vi.mock("@/lib/store", () => ({ useStore: () => ({ dataConfig: { mode: "test" } }) }));

beforeEach(() => { document.cookie = "lang=en; path=/"; });
afterEach(() => { cleanup(); document.cookie = "lang=; path=/; max-age=0"; });

describe("tracking and memory screens in English", () => {
  it("the notification centre asks for a verified session in English", () => {
    render(<LanguageProvider><NotificationCenter /></LanguageProvider>);
    expect(screen.getByText("Your notifications")).toBeInTheDocument();
    expect(screen.getByText("A verified session is needed to read notifications.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Sign in" })).toBeInTheDocument();
  });

  it("personal memory says in English that the feature is off when no assistant runtime is mounted", () => {
    render(<LanguageProvider><MemoryCenter /></LanguageProvider>);
    expect(screen.getByText("Assistant memory is not enabled in this build.")).toBeInTheDocument();
  });
});
