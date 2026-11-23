import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const get = vi.hoisted(() => vi.fn());
vi.mock("./api/client", () => ({ ApiClient: class { get = get; } }));

import { usePolicyGraphAvailable } from "./use-policy-graph-available";

function Probe() {
  return <span data-testid="state">{usePolicyGraphAvailable() ? "yes" : "no"}</span>;
}

describe("usePolicyGraphAvailable", () => {
  beforeEach(() => { get.mockReset(); });

  it("is false until the API answers, then true", async () => {
    get.mockResolvedValue({ items: [] });
    render(<Probe />);
    expect(screen.getByTestId("state").textContent).toBe("no");
    await waitFor(() => expect(screen.getByTestId("state").textContent).toBe("yes"));
    expect(get).toHaveBeenCalledWith("/v1/policy-graph/versions");
  });

  it("stays false when the runtime has no such API (404)", async () => {
    get.mockRejectedValue(new Error("404"));
    render(<Probe />);
    await waitFor(() => expect(get).toHaveBeenCalledTimes(1));
    expect(screen.getByTestId("state").textContent).toBe("no");
  });
});
