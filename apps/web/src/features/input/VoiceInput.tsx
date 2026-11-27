"use client";

import React, { useEffect, useRef, useState } from "react";
import { CAMPUS_API_BASE_URL } from "../../lib/api/base-url";

export const MAX_SECONDS = 60;
// Measured on the D6b set (evals/results/asr-20261126): WebM/Opus at 32 kbit/s keeps the word error rate under 20 %.
export const AUDIO_BITS_PER_SECOND = 32000;

export interface VoiceResult { text: string; segments: { start: number; end: number; text: string }[]; language: string; duration_s: number }

export async function transcribe(audio: Blob): Promise<VoiceResult> {
  const form = new FormData();
  form.append("audio", audio, audio.type.includes("ogg") ? "voice.ogg" : "voice.webm");
  const response = await fetch(`${CAMPUS_API_BASE_URL.replace(/\/$/, "")}/v1/input/voice:transcribe`, { method: "POST", body: form, credentials: "include" });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || "Không nhận dạng được giọng nói.");
  return body as VoiceResult;
}

export interface Recorder { start(): Promise<void>; stop(): Promise<Blob>; cancel(): void }

/** MediaRecorder on the microphone; audio stays in memory until the person sends it for recognition. */
export function microphoneRecorder(): Recorder {
  let recorder: MediaRecorder | null = null;
  let stream: MediaStream | null = null;
  let chunks: Blob[] = [];
  const release = () => { stream?.getTracks().forEach((t) => t.stop()); stream = null; };
  return {
    async start() {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const type = ["audio/webm;codecs=opus", "audio/ogg;codecs=opus", "audio/webm"].find((t) => MediaRecorder.isTypeSupported?.(t)) ?? "";
      recorder = new MediaRecorder(stream, { mimeType: type || undefined, audioBitsPerSecond: AUDIO_BITS_PER_SECOND });
      chunks = [];
      recorder.ondataavailable = (event) => { if (event.data.size) chunks.push(event.data); };
      recorder.start();
    },
    stop() {
      return new Promise<Blob>((resolve) => {
        if (!recorder) { resolve(new Blob()); return; }
        recorder.onstop = () => { release(); resolve(new Blob(chunks, { type: recorder?.mimeType || "audio/webm" })); };
        recorder.stop();
      });
    },
    cancel() { try { recorder?.stop(); } catch { /* already stopped */ } release(); chunks = []; },
  };
}

/** Speak a question: record (at most 60 s), see the recognised text, correct it, then send it yourself. Nothing is sent alone. */
export function VoiceInput({ onSend, recorder: makeRecorder = microphoneRecorder, recognize = transcribe }: {
  onSend: (message: string) => void; recorder?: () => Recorder; recognize?: (audio: Blob) => Promise<VoiceResult>;
}) {
  const [state, setState] = useState<"idle" | "recording" | "working" | "ready">("idle");
  const [seconds, setSeconds] = useState(0);
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const recorder = useRef<Recorder | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => () => { if (timer.current) clearInterval(timer.current); recorder.current?.cancel(); }, []);

  async function start() {
    setError(null); setText("");
    try {
      recorder.current = makeRecorder();
      await recorder.current.start();
      setSeconds(0); setState("recording");
      timer.current = setInterval(() => setSeconds((s) => {
        if (s + 1 >= MAX_SECONDS) void stop();
        return s + 1;
      }), 1000);
    } catch {
      setError("Không mở được micro. Hãy cho phép trình duyệt dùng micro rồi thử lại.");
      setState("idle");
    }
  }

  async function stop() {
    if (timer.current) { clearInterval(timer.current); timer.current = null; }
    if (!recorder.current) return;
    const current = recorder.current;
    recorder.current = null;
    setState("working");
    try {
      const audio = await current.stop();
      const result = await recognize(audio);
      setText(result.text); setState("ready");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Không nhận dạng được giọng nói.");
      setState("idle");
    }
  }

  return (
    <section aria-label="Hỏi bằng giọng nói" className="space-y-2">
      {state !== "recording"
        ? <button type="button" disabled={state === "working"} onClick={() => void start()}>Ghi âm câu hỏi</button>
        : <button type="button" onClick={() => void stop()}>Dừng ghi ({seconds}/{MAX_SECONDS} giây)</button>}
      <p className="text-xs">Âm thanh chỉ được nhận dạng trên máy chủ của trường và không được lưu.</p>
      {state === "working" && <p role="status">Đang nhận dạng giọng nói…</p>}
      {error && <p role="alert">{error}</p>}
      {state === "ready" && (
        <div className="space-y-2">
          <label>Câu hỏi nghe được (bạn có thể sửa)
            <textarea value={text} maxLength={2000} rows={4} onChange={(e) => setText(e.target.value)} />
          </label>
          <button type="button" disabled={!text.trim()} onClick={() => { onSend(text.trim()); setText(""); setState("idle"); }}>Gửi</button>
        </div>
      )}
    </section>
  );
}
