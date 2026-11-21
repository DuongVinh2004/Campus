"use client";
import React, { useId, useState } from "react";
import { useT } from "@/lib/i18n";
import { AccessibleDialog } from "../../components/shared/AccessibleDialog";
import { ApiClient } from "../../lib/api/client";

/** Must match CONSENT_VERSION in services/api/.../gap_reports.py; a different value is refused by the server. */
export const GAP_CONSENT_VERSION = "p2-2026-11-21";
const MAX_QUESTION = 500;

type Receipt = { delete_code: string; question: string | null; text_kept: boolean; expires_at: string };

/** "Report missing information": the student chooses to send one question, after reading what happens to it (P2). */
export function GapReport({ question, client = new ApiClient() }: { question: string; client?: Pick<ApiClient, "post"> }) {
  const t = useT();
  const titleId = useId();
  const [open, setOpen] = useState(false);
  const [text, setText] = useState(question);
  const [agreed, setAgreed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const [deleted, setDeleted] = useState(false);

  const close = () => { if (busy) return; setOpen(false); setAgreed(false); setError(""); };
  const send = async () => {
    setBusy(true); setError("");
    try {
      setReceipt(await client.post<Receipt>("/v1/answer-gap-reports", { question: text, consent: true, consent_version: GAP_CONSENT_VERSION }));
    } catch {
      setError(t("gapx.error"));
    } finally {
      setBusy(false);
    }
  };
  const remove = async () => {
    if (!receipt) return;
    setBusy(true); setError("");
    try {
      await client.post("/v1/answer-gap-reports/delete", { delete_code: receipt.delete_code });
      setDeleted(true);
    } catch {
      setError(t("gapx.deleteError"));
    } finally {
      setBusy(false);
    }
  };

  return <>
    <button type="button" className="text-xs underline bg-transparent border-0 cursor-pointer px-1 py-0.5 text-slate-600 dark:text-slate-300" onClick={() => { setText(question); setReceipt(null); setDeleted(false); setOpen(true); }}>{t("gapx.open")}</button>
    <AccessibleDialog open={open} onClose={close} preventClose={busy} labelledBy={titleId}>
      <div className="space-y-3 p-5 max-w-lg">
        <h2 id={titleId} className="text-lg font-semibold">{t("gapx.title")}</h2>
        {!receipt ? <>
          <p className="text-sm">{t("gapx.intro")}</p>
          <ul className="text-sm list-disc pl-5 space-y-1">
            <li>{t("gapx.purpose")}</li><li>{t("gapx.who")}</li><li>{t("gapx.keep")}</li><li>{t("gapx.withdraw")}</li><li>{t("gapx.warning")}</li>
          </ul>
          <label className="block text-sm">{t("gapx.question")}
            <textarea className="w-full mt-1 border rounded p-2" rows={4} maxLength={MAX_QUESTION} value={text} disabled={busy} onChange={(event) => setText(event.target.value)} />
          </label>
          <label className="flex gap-2 text-sm"><input type="checkbox" checked={agreed} disabled={busy} onChange={(event) => setAgreed(event.target.checked)} /> {t("gapx.agree")}</label>
          {error && <p role="alert" className="text-sm text-rose-600">{error}</p>}
          <div className="flex gap-2 justify-end">
            <button type="button" disabled={busy} onClick={close}>{t("gapx.cancel")}</button>
            <button type="button" disabled={busy || !agreed || text.trim().length < 3} onClick={() => void send()}>{busy ? t("gapx.sending") : t("gapx.send")}</button>
          </div>
        </> : <>
          <p role="status" className="text-sm">{deleted ? t("gapx.deleted") : t(receipt.text_kept ? "gapx.sent" : "gapx.sentNoText")}</p>
          {!deleted && <>
            {receipt.text_kept && <p className="text-sm">{t("gapx.kept")} <q>{receipt.question}</q></p>}
            <p className="text-sm">{t("gapx.code")} <code>{receipt.delete_code}</code></p>
            {error && <p role="alert" className="text-sm text-rose-600">{error}</p>}
            <button type="button" disabled={busy} onClick={() => void remove()}>{t("gapx.delete")}</button>
          </>}
          <div className="flex justify-end"><button type="button" disabled={busy} onClick={close}>{t("gapx.close")}</button></div>
        </>}
      </div>
    </AccessibleDialog>
  </>;
}
