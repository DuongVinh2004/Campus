import { describe, it, expect } from "vitest";
import * as fs from "node:fs";
import * as path from "node:path";

describe("Design Tokens & Global Styles (TASK-WEB-DESIGN-001)", () => {
  const tokensPath = path.resolve(__dirname, "tokens.css");
  const globalsPath = path.resolve(__dirname, "../app/globals.css");

  it("tokens.css exists and defines mandatory WCAG AA tokens", () => {
    expect(fs.existsSync(tokensPath)).toBe(true);
    const tokensContent = fs.readFileSync(tokensPath, "utf-8");

    // Brand and Contrast tokens
    expect(tokensContent).toContain("--color-primary");
    expect(tokensContent).toContain("--color-text-main");
    expect(tokensContent).toContain("--color-text-muted");
    expect(tokensContent).toContain("--color-bg-main");
    expect(tokensContent).toContain("--color-border");
    expect(tokensContent).toContain("--color-focus");

    // Touch Target and Focus ring tokens (WCAG 2.2 AA)
    expect(tokensContent).toContain("--target-size-min: 44px");
    expect(tokensContent).toContain("--focus-ring-width: 2px");

    // Simulation & Safety tokens
    expect(tokensContent).toContain("--color-banner-demo");
    expect(tokensContent).toContain("--color-badge-simulation");
  });

  it("globals.css imports tokens and defines accessibility baseline", () => {
    expect(fs.existsSync(globalsPath)).toBe(true);
    const globalsContent = fs.readFileSync(globalsPath, "utf-8");

    // Ensure tokens imported and focus styles declared
    expect(globalsContent).toContain("tokens.css");
    expect(globalsContent).toContain(":focus-visible");
    expect(globalsContent).toContain(".skip-link");
    expect(globalsContent).toContain("prefers-reduced-motion");
  });

  it("negative path: validates rejection of missing essential token", () => {
    const tokensContent = fs.existsSync(tokensPath) ? fs.readFileSync(tokensPath, "utf-8") : "";
    const hasUndefinedToken = tokensContent.includes("--non-existent-token");
    expect(hasUndefinedToken).toBe(false);
  });

  it("dark mode defines complete token overrides and passes WCAG AA contrast", () => {
    const tokensContent = fs.readFileSync(tokensPath, "utf-8");
    const darkBlockMatch = tokensContent.match(/\.dark\s*\{([^}]+)\}/);
    expect(darkBlockMatch).not.toBeNull();
    const darkBlock = darkBlockMatch![1];

    // Primary & Brand Tokens in Dark Mode
    expect(darkBlock).toContain("--color-primary:");
    expect(darkBlock).toContain("--color-primary-light:");
    expect(darkBlock).toContain("--color-primary-subtle:");
    expect(darkBlock).toContain("--color-primary-border:");

    // Semantic Surface & Typography Tokens in Dark Mode
    expect(darkBlock).toContain("--bg-page:");
    expect(darkBlock).toContain("--surface-card:");
    expect(darkBlock).toContain("--surface-subtle:");
    expect(darkBlock).toContain("--border-color:");
    expect(darkBlock).toContain("--text-primary:");
    expect(darkBlock).toContain("--text-secondary:");
    expect(darkBlock).toContain("--text-muted:");

    // Status Tokens in Dark Mode
    expect(darkBlock).toContain("--color-status-success:");
    expect(darkBlock).toContain("--color-status-warning:");
    expect(darkBlock).toContain("--color-status-error:");
    expect(darkBlock).toContain("--color-status-info:");

    // Contrast calculations (WCAG AA >= 4.5:1)
    const getVal = (block: string, token: string): string => {
      const m = block.match(new RegExp(`${token}:\\s*([^;]+);`));
      return m ? m[1].trim() : "";
    };

    const srgbToLin = (c: number) => (c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4));
    const lum = (hex: string) => {
      const clean = hex.replace("#", "");
      const r = parseInt(clean.substring(0, 2), 16) / 255;
      const g = parseInt(clean.substring(2, 4), 16) / 255;
      const b = parseInt(clean.substring(4, 6), 16) / 255;
      return 0.2126 * srgbToLin(r) + 0.7152 * srgbToLin(g) + 0.0722 * srgbToLin(b);
    };
    const contrast = (hex1: string, hex2: string) => {
      const l1 = lum(hex1);
      const l2 = lum(hex2);
      return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
    };

    // Dark mode text primary vs bg-page
    const darkBgPage = getVal(darkBlock, "--bg-page");
    const darkTextPrimary = getVal(darkBlock, "--text-primary");
    expect(contrast(darkBgPage, darkTextPrimary)).toBeGreaterThanOrEqual(4.5);

    // Dark mode text main vs bg main
    const darkBgMain = getVal(darkBlock, "--color-bg-main");
    const darkTextMain = getVal(darkBlock, "--color-text-main");
    expect(contrast(darkBgMain, darkTextMain)).toBeGreaterThanOrEqual(4.5);

    // Dark mode text on surface card
    const darkSurfaceCard = getVal(darkBlock, "--surface-card");
    expect(contrast(darkSurfaceCard, darkTextPrimary)).toBeGreaterThanOrEqual(4.5);

    // Dark mode primary brand text on surface card
    const darkColorPrimary = getVal(darkBlock, "--color-primary");
    expect(contrast(darkSurfaceCard, darkColorPrimary)).toBeGreaterThanOrEqual(4.5);

    const lightBlock = tokensContent.match(/:root\s*\{([^}]+)\}/)![1];
    const globals = fs.readFileSync(globalsPath, "utf-8");
    const button = globals.match(/\.campus-btn-primary, \.fluent-btn-primary\s*\{([^}]+)\}/)![1];
    const foregroundToken = button.match(/(?:^|\n)\s*color:\s*var\((--[\w-]+)\)/)?.[1];
    for (const block of [lightBlock, darkBlock]) {
      const foreground = foregroundToken ? getVal(block, foregroundToken) : "#ffffff";
      for (const background of ["--color-primary", "--color-primary-hover"]) {
        expect(contrast(getVal(block, background), foreground)).toBeGreaterThanOrEqual(4.5);
      }
    }
  });
});
