import React from "react";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { LanguageToggle } from "../../components/LanguageToggle";
import { en } from "./en";
import { LanguageProvider, interpolate, parseLanguage, translate, useT } from "./index";
import { vi } from "./vi";

function clearCookie() {
  document.cookie = "lang=; path=/; max-age=0";
}

beforeEach(() => { clearCookie(); document.documentElement.lang = "vi"; });
afterEach(() => { cleanup(); clearCookie(); });

describe("translate", () => {
  it("returns the text of the language and fills placeholders", () => {
    expect(translate("vi", "nav.rooms")).toBe("Phòng học");
    expect(translate("en", "nav.rooms")).toBe("Rooms");
  });

  it("fills named placeholders and leaves unknown ones visible", () => {
    expect(interpolate("Còn {n} ngày — {who}", { n: 3, who: "An" })).toBe("Còn 3 ngày — An");
    expect(interpolate("Còn {n} ngày", {})).toBe("Còn {n} ngày");
    expect(interpolate("Không có tham số {n}")).toBe("Không có tham số {n}");
    expect(translate("vi", "lang.sourceNote", { x: 1 })).toBe(vi["lang.sourceNote"]);
  });

  it("falls back to Vietnamese for a language it does not know", () => {
    expect(translate("fr" as never, "nav.rooms")).toBe("Phòng học");
  });

  it("only accepts the two languages from a cookie", () => {
    expect(parseLanguage("en")).toBe("en");
    expect(parseLanguage("vi")).toBe("vi");
    for (const bad of ["EN", "fr", "", null, undefined, "en;x"]) expect(parseLanguage(bad as never)).toBe("vi");
  });
});

describe("the two dictionaries", () => {
  it("have exactly the same keys (a missing English key is also a compile error)", () => {
    expect(Object.keys(en).sort()).toEqual(Object.keys(vi).sort());
  });

  it("have no empty text", () => {
    for (const dictionary of [vi, en]) for (const [key, text] of Object.entries(dictionary)) expect(text.trim().length, key).toBeGreaterThan(0);
  });

  it("keep the same placeholders in both languages", () => {
    const names = (text: string) => [...text.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();
    for (const key of Object.keys(vi) as (keyof typeof vi)[]) expect(names(en[key]), key).toEqual(names(vi[key]));
  });
});

function Probe() {
  const t = useT();
  return <p data-testid="text">{t("nav.schedule")}</p>;
}

describe("LanguageProvider", () => {
  it("starts in Vietnamese, switches to English, remembers it in a cookie and sets <html lang>", () => {
    render(<LanguageProvider><LanguageToggle /><Probe /></LanguageProvider>);
    expect(screen.getByTestId("text").textContent).toBe("Lịch học");
    fireEvent.click(screen.getByRole("button", { name: "Chuyển sang tiếng Anh" }));
    expect(screen.getByTestId("text").textContent).toBe("Timetable");
    expect(document.documentElement.lang).toBe("en");
    expect(document.cookie).toContain("lang=en");
    fireEvent.click(screen.getByRole("button", { name: "Switch to Vietnamese" }));
    expect(screen.getByTestId("text").textContent).toBe("Lịch học");
    expect(document.documentElement.lang).toBe("vi");
  });

  it("reads the choice made on an earlier visit", () => {
    document.cookie = "lang=en; path=/";
    render(<LanguageProvider><Probe /></LanguageProvider>);
    expect(screen.getByTestId("text").textContent).toBe("Timetable");
    expect(document.documentElement.lang).toBe("en");
  });

  it("ignores a cookie that is not one of the two languages", () => {
    document.cookie = "lang=de; path=/";
    render(<LanguageProvider><Probe /></LanguageProvider>);
    expect(screen.getByTestId("text").textContent).toBe("Lịch học");
  });

  it("works without a provider (Vietnamese) so a component can be rendered on its own", () => {
    render(<Probe />);
    expect(screen.getByTestId("text").textContent).toBe("Lịch học");
    act(() => undefined);
  });
});
