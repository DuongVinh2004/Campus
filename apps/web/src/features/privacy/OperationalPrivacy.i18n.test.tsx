import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { LanguageProvider } from "../../lib/i18n";
import { OperationalPrivacy } from "./OperationalPrivacy";

vi.mock("next/link", () => ({ default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => <a href={href} {...rest}>{children}</a> }));
vi.mock("@/components/AppShell", () => ({ AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div> }));
vi.mock("@/lib/api/client", () => ({
  ApiClient: class {
    async get(path: string) {
      if (path.endsWith("/notice")) {
        return { version: "1", effective_at: "2026-01-01", data_categories: ["ACCOUNT_CONTEXT"], purposes: ["SERVICE_DELIVERY"], retention_summary: [{ data_class: "AUDIT_METADATA", retention: "1y", configured_rule: "R1" }] };
      }
      return { items: [{ id: "c1", purpose: "QUALITY_FEEDBACK", decision: "GRANTED", notice_version: "1", recorded_at: "2026-01-02T00:00:00Z" }] };
    }
  },
}));

beforeEach(() => { document.cookie = "lang=en; path=/"; });
afterEach(() => { cleanup(); document.cookie = "lang=; path=/; max-age=0"; });

describe("privacy page in English", () => {
  it("translates headings and the code labels", async () => {
    render(<LanguageProvider><OperationalPrivacy /></LanguageProvider>);
    expect(await screen.findByRole("heading", { name: "Privacy & personal data" })).toBeInTheDocument();
    expect(screen.getByText("Account information")).toBeInTheDocument();
    expect(screen.getByText("Service delivery")).toBeInTheDocument();
    expect(screen.getByText("Improving answer quality")).toBeInTheDocument();
    expect(screen.getByText("Agreed")).toBeInTheDocument();
    expect(screen.getByText(/Audit log: 1y \(rule R1\)/)).toBeInTheDocument();
    expect(screen.getByText("My requests")).toBeInTheDocument();
  });
});
