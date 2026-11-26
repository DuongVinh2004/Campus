"use client";

import React, { useRef, useState } from "react";
import { CAMPUS_API_BASE_URL } from "../../lib/api/base-url";

export const MAX_SIDE = 2000;
export const MAX_TEXT = 2000;

export interface OcrLine { text: string; confidence: number; bbox: number[] }
export interface OcrResult { text: string; lines: OcrLine[]; mean_confidence: number; warnings: string[] }

/** Target size that keeps the long edge at or below MAX_SIDE. */
export function fitSize(width: number, height: number): { width: number; height: number } {
  const scale = Math.min(1, MAX_SIDE / Math.max(width, height));
  return { width: Math.max(1, Math.round(width * scale)), height: Math.max(1, Math.round(height * scale)) };
}

/** Redraw to a fresh canvas and export PNG: drops EXIF and GPS before anything leaves the device. */
export async function imageToPng(file: Blob): Promise<Blob> {
  const bitmap = await createImageBitmap(file);
  const { width, height } = fitSize(bitmap.width, bitmap.height);
  const canvas = document.createElement("canvas");
  canvas.width = width; canvas.height = height;
  canvas.getContext("2d")!.drawImage(bitmap, 0, 0, width, height);
  return new Promise((resolve, reject) => canvas.toBlob(b => (b ? resolve(b) : reject(new Error("PNG_EXPORT_FAILED"))), "image/png"));
}

export async function ocrImage(png: Blob): Promise<OcrResult> {
  const form = new FormData();
  form.append("image", png, "image.png");
  const response = await fetch(`${CAMPUS_API_BASE_URL.replace(/\/$/, "")}/v1/input/image:ocr`, { method: "POST", body: form, credentials: "include" });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || "Không đọc được ảnh.");
  return body as OcrResult;
}

export function composeMessage(question: string, confirmedText: string): string {
  const text = confirmedText.trim().slice(0, MAX_TEXT);
  return text ? `${question.trim()}\n\nNội dung từ ảnh (đã xác nhận):\n${text}` : question.trim();
}

export function ImageInput({ onSend, convert = imageToPng, recognize = ocrImage }: {
  onSend: (message: string) => void; convert?: (file: Blob) => Promise<Blob>; recognize?: (png: Blob) => Promise<OcrResult>;
}) {
  const [result, setResult] = useState<OcrResult | null>(null);
  const [text, setText] = useState("");
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);

  const pick = async (file: File | undefined) => {
    if (!file) return;
    setBusy(true); setError(null); setResult(null);
    try {
      const read = await recognize(await convert(file));
      setResult(read); setText(read.text);
    } catch (e) { setError(e instanceof Error ? e.message : "Không đọc được ảnh."); } finally { setBusy(false); if (input.current) input.current.value = ""; }
  };

  return (
    <section aria-label="Hỏi bằng ảnh" className="space-y-2">
      <label>Chọn hoặc chụp ảnh
        <input ref={input} type="file" accept="image/*" capture="environment" onChange={e => void pick(e.target.files?.[0])} />
      </label>
      {busy && <p role="status">Đang đọc chữ trong ảnh…</p>}
      {error && <p role="alert">{error}</p>}
      {result && (
        <div className="space-y-2">
          {result.warnings.includes("LOW_CONFIDENCE") && <p role="status">Ảnh khó đọc; hãy kiểm tra kỹ chữ bên dưới trước khi gửi.</p>}
          <label>Chữ đọc được (bạn có thể sửa)
            <textarea value={text} maxLength={MAX_TEXT} rows={6} onChange={e => setText(e.target.value)} />
          </label>
          <label>Câu hỏi của bạn
            <input type="text" value={question} onChange={e => setQuestion(e.target.value)} />
          </label>
          <button disabled={!question.trim()} onClick={() => onSend(composeMessage(question, text))}>Gửi</button>
        </div>
      )}
    </section>
  );
}
