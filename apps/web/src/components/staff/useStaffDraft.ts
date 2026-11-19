"use client";

import { useEffect, useRef, useState } from "react";

// Session-only, isolated by account and record. No additional browser persistence.
const drafts = new Map<string, { text: string; saved: string }>();
export function useStaffDraft(key: string, initial: string) {
  const [draft, setDraft] = useState(() => drafts.get(key) || { text: initial, saved: initial });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const busy = useRef(false);
  const current = useRef(draft);
  const activeKey = useRef(key);
  const mounted = useRef(true);
  const dirty = draft.text !== draft.saved;
  useEffect(() => {
    activeKey.current = key;
    const value = drafts.get(key) || { text: initial, saved: initial };
    current.current = value; setDraft(value); setError("");
  }, [key]);
  useEffect(() => {
    mounted.current = true;
    const warn = (event: BeforeUnloadEvent) => { if (current.current.text !== current.current.saved) { event.preventDefault(); event.returnValue = ""; } };
    window.addEventListener("beforeunload", warn);
    return () => { mounted.current = false; window.removeEventListener("beforeunload", warn); };
  }, []);
  function change(text: string) { const value = { ...current.current, text }; current.current = value; drafts.set(key, value); setDraft(value); setError(""); }
  async function save(write: (text: string) => Promise<void>) {
    if (busy.current) return;
    busy.current = true; setSaving(true); setError("");
    const text = current.current.text;
    const startedKey = key;
    try { await write(text); const value = { text: drafts.get(startedKey)?.text ?? text, saved: text }; drafts.set(startedKey, value); if (mounted.current && activeKey.current === startedKey) { current.current = value; setDraft(value); } }
    catch (e) { if (mounted.current && activeKey.current === startedKey) setError(e instanceof Error ? e.message : "Chưa lưu được nháp. Nội dung vẫn được giữ trong phiên."); }
    finally { busy.current = false; if (mounted.current) setSaving(false); }
  }
  return { text: draft.text, change, dirty, saving, error, save };
}
