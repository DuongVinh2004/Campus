"use client";

import { useState } from "react";
import { UploadCloud } from "lucide-react";

export function FileAttachmentInput({ id, disabled, invalid, onFile }: { id: string; disabled: boolean; invalid?: boolean; onFile: (file?: File) => void }) {
  const [dragging, setDragging] = useState(false);
  return <div className={"campus-upload-target" + (dragging ? " is-dragging" : "")} onDragOver={event => { event.preventDefault(); if (!disabled) setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={event => { event.preventDefault(); setDragging(false); if (!disabled) onFile(event.dataTransfer.files[0]); }}>
    <UploadCloud size={26} aria-hidden="true" /><strong>Chọn tệp hoặc kéo thả tại đây</strong><span>Tệp văn bản .txt · nội dung sẽ được kiểm tra trước khi thêm</span>
    <input id={id} type="file" accept=".txt,text/plain" disabled={disabled} aria-invalid={invalid} onChange={event => { onFile(event.target.files?.[0]); event.target.value = ""; }} />
  </div>;
}
