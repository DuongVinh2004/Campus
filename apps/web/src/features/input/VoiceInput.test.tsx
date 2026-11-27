import React from "react";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MAX_SECONDS, VoiceInput, type Recorder } from "./VoiceInput";

afterEach(() => { cleanup(); vi.useRealTimers(); });

function fakeRecorder(): { make: () => Recorder; stopped: () => number } {
  let stops = 0;
  return {
    make: () => ({ start: async () => undefined, stop: async () => { stops++; return new Blob(["x"], { type: "audio/webm" }); }, cancel: () => undefined }),
    stopped: () => stops,
  };
}

describe("VoiceInput", () => {
  it("never sends by itself: the recognised text is shown for correction and goes out only with Gửi", async () => {
    const onSend = vi.fn();
    const rec = fakeRecorder();
    const recognize = vi.fn().mockResolvedValue({ text: "học phí kỳ này bao nhiêu", segments: [], language: "vi", duration_s: 3 });
    render(<VoiceInput onSend={onSend} recorder={rec.make} recognize={recognize} />);
    fireEvent.click(screen.getByRole("button", { name: "Ghi âm câu hỏi" }));
    fireEvent.click(await screen.findByRole("button", { name: /Dừng ghi/ }));
    const box = await screen.findByLabelText("Câu hỏi nghe được (bạn có thể sửa)");
    expect((box as HTMLTextAreaElement).value).toBe("học phí kỳ này bao nhiêu");
    expect(onSend).not.toHaveBeenCalled();
    fireEvent.change(box, { target: { value: "học phí học kỳ này bao nhiêu" } });
    fireEvent.click(screen.getByRole("button", { name: "Gửi" }));
    expect(onSend).toHaveBeenCalledWith("học phí học kỳ này bao nhiêu");
    expect(recognize).toHaveBeenCalledTimes(1);
  });

  it("stops by itself at 60 seconds", async () => {
    vi.useFakeTimers();
    const rec = fakeRecorder();
    render(<VoiceInput onSend={() => undefined} recorder={rec.make} recognize={async () => ({ text: "a", segments: [], language: "vi", duration_s: 60 })} />);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Ghi âm câu hỏi" })); });
    await act(async () => { vi.advanceTimersByTime(MAX_SECONDS * 1000); });
    expect(rec.stopped()).toBe(1);
  });

  it("explains a refused microphone and a recognizer error in plain words", async () => {
    const denied: () => Recorder = () => ({ start: async () => { throw new Error("NotAllowedError"); }, stop: async () => new Blob(), cancel: () => undefined });
    render(<VoiceInput onSend={() => undefined} recorder={denied} />);
    fireEvent.click(screen.getByRole("button", { name: "Ghi âm câu hỏi" }));
    expect((await screen.findByRole("alert")).textContent).toContain("Không mở được micro");
    cleanup();
    const rec = fakeRecorder();
    render(<VoiceInput onSend={() => undefined} recorder={rec.make} recognize={async () => { throw new Error("Nhận dạng giọng nói chưa sẵn sàng."); }} />);
    fireEvent.click(screen.getByRole("button", { name: "Ghi âm câu hỏi" }));
    fireEvent.click(await screen.findByRole("button", { name: /Dừng ghi/ }));
    expect((await screen.findByRole("alert")).textContent).toBe("Nhận dạng giọng nói chưa sẵn sàng.");
  });
});
