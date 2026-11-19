import React from "react";
import { act, cleanup, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { usePolling } from "./use-polling";

function Probe({ task }: { task: () => void }) { usePolling(task, 1000); return null; }
function setHidden(value: boolean) { Object.defineProperty(document, "hidden", { configurable: true, get: () => value }); }

describe("usePolling", () => {
  beforeEach(() => { vi.useFakeTimers(); setHidden(false); });
  afterEach(() => { cleanup(); vi.useRealTimers(); setHidden(false); });

  it("runs at once and then on every interval while the tab is visible", () => {
    const task = vi.fn();
    render(<Probe task={task} />);
    expect(task).toHaveBeenCalledTimes(1);
    act(() => { vi.advanceTimersByTime(3000); });
    expect(task).toHaveBeenCalledTimes(4);
  });

  it("makes no request while the tab is hidden, and refreshes once when it comes back", () => {
    const task = vi.fn();
    render(<Probe task={task} />);
    setHidden(true);
    act(() => { vi.advanceTimersByTime(5000); });
    expect(task).toHaveBeenCalledTimes(1);
    setHidden(false);
    act(() => { document.dispatchEvent(new Event("visibilitychange")); });
    expect(task).toHaveBeenCalledTimes(2);
  });

  it("stops after unmount", () => {
    const task = vi.fn();
    const view = render(<Probe task={task} />);
    view.unmount();
    act(() => { vi.advanceTimersByTime(5000); });
    expect(task).toHaveBeenCalledTimes(1);
  });
});
