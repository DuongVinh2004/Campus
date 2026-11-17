import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ReminderPreferences } from "./ReminderPreferences";

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const problem = (status: number, detail: string) => json(status, { type: "x", title: "t", status, detail, code: "X" });

describe("ReminderPreferences", () => {
  it("shows a switch per kind with its current state", async () => {
    fetchMock.mockResolvedValue(json(200, { exam: true, sources: false }));
    render(<ReminderPreferences kinds={["exam", "sources"]} />);
    const exam = await screen.findByRole("switch", { name: "Nhắc lịch thi" });
    expect(exam.getAttribute("aria-checked")).toBe("true");
    expect(screen.getByRole("switch", { name: "Nhắc rà soát nguồn tri thức" }).getAttribute("aria-checked")).toBe("false");
    expect(exam.getAttribute("aria-describedby")).toBe("pref-exam-help");
  });

  it("shows only the kinds asked for", async () => {
    fetchMock.mockResolvedValue(json(200, { exam: true, sources: true }));
    render(<ReminderPreferences />);
    await screen.findByRole("switch", { name: "Nhắc lịch thi" });
    expect(screen.queryByRole("switch", { name: /nguồn/ })).toBeNull();
  });

  it("sends only the changed kind and shows what the server answers", async () => {
    fetchMock.mockResolvedValueOnce(json(200, { exam: true, sources: true }));
    fetchMock.mockResolvedValueOnce(json(200, { exam: false, sources: true }));
    render(<ReminderPreferences />);
    fireEvent.click(await screen.findByRole("switch", { name: "Nhắc lịch thi" }));
    await waitFor(() => expect(screen.getByRole("switch", { name: "Nhắc lịch thi" }).getAttribute("aria-checked")).toBe("false"));
    const [url, init] = fetchMock.mock.calls[1];
    expect(url).toBe("/v1/notifications/preferences");
    expect((init as RequestInit).method).toBe("PUT");
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({ exam: false });
  });

  it("undoes the change and says so when the server refuses it", async () => {
    fetchMock.mockResolvedValueOnce(json(200, { exam: true, sources: true }));
    fetchMock.mockResolvedValueOnce(problem(500, "Máy chủ lỗi."));
    render(<ReminderPreferences />);
    fireEvent.click(await screen.findByRole("switch", { name: "Nhắc lịch thi" }));
    expect((await screen.findByRole("alert")).textContent).toContain("Máy chủ lỗi");
    expect(screen.getByRole("switch", { name: "Nhắc lịch thi" }).getAttribute("aria-checked")).toBe("true");
  });

  it("explains when the settings cannot be loaded", async () => {
    fetchMock.mockRejectedValue(new Error("offline"));
    render(<ReminderPreferences />);
    expect((await screen.findByRole("alert")).textContent).toContain("Không tải được");
  });

  it("ignores a second click while the first is being saved", async () => {
    let release: (value: Response) => void = () => undefined;
    fetchMock.mockResolvedValueOnce(json(200, { exam: true, sources: true }));
    fetchMock.mockReturnValueOnce(new Promise<Response>((resolve) => (release = resolve)));
    render(<ReminderPreferences />);
    const toggle = await screen.findByRole("switch", { name: "Nhắc lịch thi" });
    fireEvent.click(toggle);
    fireEvent.click(toggle);
    expect(fetchMock).toHaveBeenCalledTimes(2); // the load and one save
    release(json(200, { exam: false, sources: true }));
    await waitFor(() => expect(screen.getByRole("switch", { name: "Nhắc lịch thi" }).getAttribute("aria-checked")).toBe("false"));
  });
});
