import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const get = vi.hoisted(() => vi.fn());
vi.mock("./api/client", () => ({ ApiClient: class { get = get; } }));

import { useSourceReviewStates } from "./use-source-review-states";

function Probe({ ids, enabled = true }: { ids: string[]; enabled?: boolean }) {
  return <span data-testid="s">{JSON.stringify(useSourceReviewStates(ids, enabled))}</span>;
}

describe("useSourceReviewStates", () => {
  beforeEach(() => { get.mockReset(); });

  it("asks once for the distinct ids and returns their states", async () => {
    get.mockResolvedValue({ states: { a: "OVERDUE" } });
    render(<Probe ids={["a", "b", "a"]} />);
    await waitFor(() => expect(screen.getByTestId("s").textContent).toBe('{"a":"OVERDUE"}'));
    expect(get).toHaveBeenCalledTimes(1);
    expect(get.mock.calls[0][0]).toBe("/v1/knowledge/source-review-status?source_ids=a%2Cb");
  });

  it("returns no labels when the lookup fails, and does nothing when disabled or empty", async () => {
    get.mockRejectedValue(new Error("down"));
    render(<Probe ids={["a"]} />);
    await waitFor(() => expect(get).toHaveBeenCalledTimes(1));
    expect(screen.getByTestId("s").textContent).toBe("{}");
    render(<Probe ids={["a"]} enabled={false} />);
    render(<Probe ids={[]} />);
    expect(get).toHaveBeenCalledTimes(1);
  });
});
