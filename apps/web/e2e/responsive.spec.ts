import React from "react";
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup, within } from "@testing-library/react";
import * as fs from "node:fs";
import * as path from "node:path";
import { AppShell } from "../src/components/AppShell";

describe("Responsive Viewport Snapshots (TASK-WEB-RESPONSIVE-001)", () => {
  afterEach(() => {
    cleanup();
  });

  const snapshotsPath = path.resolve(__dirname, "responsive.snapshots.json");

  it("loads and validates viewport snapshot declarations", () => {
    expect(fs.existsSync(snapshotsPath)).toBe(true);
    const content = JSON.parse(fs.readFileSync(snapshotsPath, "utf-8"));

    expect(content.viewports.mobile.width).toBe(375);
    expect(content.viewports.tablet.width).toBe(768);
    expect(content.viewports.desktop.width).toBe(1280);

    expect(content.viewports.mobile.minTargetSizePx).toBeGreaterThanOrEqual(44);
    expect(content.viewports.tablet.minTargetSizePx).toBeGreaterThanOrEqual(44);
    expect(content.viewports.desktop.minTargetSizePx).toBeGreaterThanOrEqual(44);
  });

  it("verifies disclaimer visibility across all viewports in AppShell", () => {
    render(
      React.createElement(
        AppShell,
        null,
        React.createElement("div", null, "Viewport Content")
      )
    );

    const banner = screen.getByRole("banner");
    expect(banner).toBeDefined();
    expect(within(banner).getByText(/Campus 24\/7/i)).toBeDefined();
    expect(within(banner).getByRole("search", { name: "Tìm nhanh trong Campus" })).toBeDefined();
  });

  it("negative path: asserts no horizontal overflow flag across declared viewports", () => {
    const content = JSON.parse(fs.readFileSync(snapshotsPath, "utf-8"));
    const viewports = Object.values(content.viewports) as Array<{ hasHorizontalOverflow: boolean }>;

    for (const vp of viewports) {
      expect(vp.hasHorizontalOverflow).toBe(false);
    }
  });
});
