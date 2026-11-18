import { cleanup } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { fieldLabel } from "@/lib/ticket-labels";

afterEach(() => cleanup());

describe("ticket labels", () => {
  it("translates the form field keys and keeps an unknown key visible", () => {
    expect(fieldLabel("purpose")).toBe("Mục đích sử dụng");
    expect(fieldLabel("recipient")).toBe("Đơn vị nhận");
    expect(fieldLabel("reason")).toBe("Nội dung / lý do");
    expect(fieldLabel("something_new")).toBe("something_new");
  });
});
