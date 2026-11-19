import React from "react";
import { act, render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const clear = vi.hoisted(() => vi.fn());
vi.mock("@/components/PwaRegister", () => ({ clearPwaCaches: clear, PwaRegister: () => null }));
vi.mock("./data/create-gateway", () => ({ createGateway: () => { throw new Error("no gateway in this test"); } }));

import { StoreProvider, useStore } from "./store";

describe("signing out", () => {
  it("asks the service worker to forget its cached pages exactly once", () => {
    let logout: () => void = () => {};
    function Probe() {
      logout = useStore().logout;
      return null;
    }
    render(<StoreProvider><Probe /></StoreProvider>);
    act(() => logout());
    expect(clear).toHaveBeenCalledTimes(1);
  });
});
