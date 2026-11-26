"use client";

import React, { useCallback, useEffect, useState } from "react";

const RATES = [0.8, 1, 1.25] as const;

/** Reading the answer aloud: only on-device Vietnamese voices; nothing is sent to a server. */
export function speakableText(text: string): string {
  return text.replace(/\[CIT-\d+\]/g, "").replace(/[*_`#>]/g, "").replace(/\s+/g, " ").trim();
}

export function pickLocalVietnameseVoice(voices: SpeechSynthesisVoice[]): SpeechSynthesisVoice | null {
  return voices.find(v => v.lang.toLowerCase().startsWith("vi") && v.localService) ?? null;
}

export function ReadAloud({ text }: { text: string }) {
  const [voice, setVoice] = useState<SpeechSynthesisVoice | null>(null);
  const [ready, setReady] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [rate, setRate] = useState<number>(1);

  useEffect(() => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) { setReady(true); return; }
    const synth = window.speechSynthesis;
    const load = () => { setVoice(pickLocalVietnameseVoice(synth.getVoices())); setReady(true); };
    load();
    synth.addEventListener?.("voiceschanged", load);
    return () => { synth.removeEventListener?.("voiceschanged", load); synth.cancel(); };
  }, []);

  const start = useCallback(() => {
    if (!voice) return;
    const utterance = new SpeechSynthesisUtterance(speakableText(text));
    utterance.voice = voice; utterance.lang = voice.lang; utterance.rate = rate;
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
    setSpeaking(true);
  }, [voice, text, rate]);

  const stop = useCallback(() => { window.speechSynthesis.cancel(); setSpeaking(false); }, []);

  if (!ready) return null;
  if (!voice) return <p><small>Thiết bị chưa có giọng đọc tiếng Việt.</small></p>;
  return (
    <div role="group" aria-label="Đọc to câu trả lời">
      {speaking ? <button onClick={stop}>Dừng đọc</button> : <button onClick={start}>Đọc to</button>}
      <label> Tốc độ
        <select value={rate} onChange={e => setRate(Number(e.target.value))}>
          {RATES.map(r => <option key={r} value={r}>{r}×</option>)}
        </select>
      </label>
    </div>
  );
}
