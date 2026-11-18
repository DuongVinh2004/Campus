"use client";

import { useState } from "react";
import { Download, Paperclip } from "lucide-react";
import { readLocalAttachment } from "@/lib/local-attachments";
import type { StoredAttachment } from "@/lib/types";
import { secondaryButton } from "./StudentFlowUI";

export function AttachmentDownload({ attachment, ownerId }: { attachment: StoredAttachment; ownerId: string }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function download() {
    if (busy) return;
    setBusy(true); setError("");
    try {
      const blob = await readLocalAttachment(ownerId, attachment.id);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url; link.download = attachment.name; link.click();
      setTimeout(() => URL.revokeObjectURL(url), 30000);
    } catch (failure) { setError(failure instanceof Error ? failure.message : "Chưa tải được tệp. Hãy thử lại."); }
    finally { setBusy(false); }
  }
  return <div className="min-w-0">
    <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-slate-200 p-3 dark:border-slate-700">
      <div className="flex min-w-0 flex-1 items-start gap-2"><Paperclip className="mt-1 h-4 w-4 shrink-0 text-slate-500" aria-hidden="true" /><div className="min-w-0"><p className="break-all text-sm font-medium">{attachment.name}</p><p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{attachment.size < 1024 * 1024 ? `${Math.ceil(attachment.size / 1024)} KB` : `${(attachment.size / (1024 * 1024)).toFixed(1)} MB`}</p></div></div>
      <button type="button" disabled={busy} onClick={() => void download()} aria-label={`Tải tệp ${attachment.name}`} className={`${secondaryButton} shrink-0`}><Download className="h-4 w-4" aria-hidden="true" />{busy ? "Đang tải…" : "Tải tệp"}</button>
    </div>
    {error && <p role="alert" className="mt-2 text-sm text-red-700 dark:text-red-300">{error}</p>}
  </div>;
}
