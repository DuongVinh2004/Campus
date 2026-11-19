import React from "react";
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const clear = vi.hoisted(() => vi.fn());
vi.mock("@/components/PwaRegister", () => ({ clearPwaCaches: clear, PwaRegister: () => null }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }), useSearchParams: () => new URLSearchParams() }));

import LoginPage from "./page";

afterEach(() => { cleanup(); clear.mockReset(); });

describe("arriving at the sign-in page", () => {
  it("makes the service worker forget its cached pages, once (the operational build has no sign-out button)", () => {
    render(<LoginPage />);
    expect(clear).toHaveBeenCalledTimes(1);
  });
});
