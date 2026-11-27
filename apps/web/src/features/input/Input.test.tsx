import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ImageInput, composeMessage, fitSize } from "./ImageInput";
import { ReadAloud, pickLocalVietnameseVoice, speakableText } from "./ReadAloud";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("image input", () => {
  it("keeps the long edge within 2000 px and composes the confirmed text after the question", () => {
    expect(fitSize(4000, 3000)).toEqual({ width: 2000, height: 1500 });
    expect(fitSize(800, 600)).toEqual({ width: 800, height: 600 });
    expect(composeMessage(" Hạn nộp khi nào? ", "Học phí trước 15/12")).toBe("Hạn nộp khi nào?\n\nNội dung từ ảnh (đã xác nhận):\nHọc phí trước 15/12");
    expect(composeMessage("Hỏi", "x".repeat(3000)).length).toBeLessThan(2100);
  });

  it("shows what was read, lets the person correct it, and sends only after the click", async () => {
    const onSend = vi.fn();
    const recognize = vi.fn().mockResolvedValue({ text: "Hoc phi 15/12", lines: [], mean_confidence: 0.4, warnings: ["LOW_CONFIDENCE"] });
    render(<ImageInput onSend={onSend} convert={async f => f} recognize={recognize} />);
    const file = new File([new Uint8Array([1, 2, 3])], "a.png", { type: "image/png" });
    fireEvent.change(screen.getByLabelText(/Chọn hoặc chụp ảnh/), { target: { files: [file] } });
    const box = await screen.findByLabelText(/Chữ đọc được/);
    expect(screen.getByText(/Ảnh khó đọc/)).toBeTruthy();
    fireEvent.change(box, { target: { value: "Học phí 15/12" } });
    fireEvent.change(screen.getByLabelText(/Câu hỏi của bạn/), { target: { value: "Hạn nộp?" } });
    expect(onSend).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Gửi" }));
    expect(onSend).toHaveBeenCalledWith("Hạn nộp?\n\nNội dung từ ảnh (đã xác nhận):\nHọc phí 15/12");
  });

  it("reports a failure without losing the page", async () => {
    render(<ImageInput onSend={vi.fn()} convert={async f => f} recognize={async () => { throw new Error("Chức năng đọc ảnh chưa sẵn sàng."); }} />);
    fireEvent.change(screen.getByLabelText(/Chọn hoặc chụp ảnh/), { target: { files: [new File([new Uint8Array([1])], "a.png")] } });
    await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("chưa sẵn sàng"));
  });
});

describe("read aloud", () => {
  const voice = (lang: string, localService: boolean) => ({ lang, localService, name: lang }) as SpeechSynthesisVoice;

  it("strips citation markers and picks only an on-device Vietnamese voice", () => {
    expect(speakableText("Nộp học phí trước 15/12 [CIT-001] **đúng hạn**")).toBe("Nộp học phí trước 15/12 đúng hạn");
    expect(pickLocalVietnameseVoice([voice("vi-VN", false), voice("en-US", true)])).toBeNull();
    expect(pickLocalVietnameseVoice([voice("en-US", true), voice("vi-VN", true)])?.lang).toBe("vi-VN");
  });

  it("hides the button with a note when the device has no Vietnamese voice, shows it when it has", async () => {
    const synth = { getVoices: () => [voice("en-US", true)], addEventListener: vi.fn(), removeEventListener: vi.fn(), cancel: vi.fn(), speak: vi.fn() };
    Object.defineProperty(window, "speechSynthesis", { value: synth, configurable: true });
    render(<ReadAloud text="Xin chào" />);
    expect(await screen.findByText(/chưa có giọng đọc tiếng Việt/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Đọc to" })).toBeNull();
    cleanup();
    synth.getVoices = () => [voice("vi-VN", true)];
    vi.stubGlobal("SpeechSynthesisUtterance", function (this: { text: string }, t: string) { this.text = t; });
    render(<ReadAloud text="Xin chào [CIT-002]" />);
    fireEvent.click(await screen.findByRole("button", { name: "Đọc to" }));
    expect(synth.speak).toHaveBeenCalledTimes(1);
    expect((synth.speak.mock.calls[0][0] as { text: string }).text).toBe("Xin chào");
  });
});
