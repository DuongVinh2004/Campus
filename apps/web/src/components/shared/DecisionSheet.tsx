"use client";

import { useEffect, useId, useState, type ReactNode } from "react";
import { ClipboardCheck, X } from "lucide-react";
import { AccessibleDialog } from "./AccessibleDialog";

export function DecisionSheet({ children, busy, version }: { children: ReactNode; busy: boolean; version: number }) {
  const [open, setOpen] = useState(false);
  const titleId = useId();
  useEffect(() => { setOpen(false); }, [version]);
  return <><button type="button" disabled={busy} className="campus-decision-trigger fluent-btn-primary" onClick={() => setOpen(true)}><ClipboardCheck size={18} />Xử lý hồ sơ</button><AccessibleDialog open={open} onClose={() => setOpen(false)} preventClose={busy} labelledBy={titleId} className="campus-decision-sheet campus-case-decision"><header className="flex items-center justify-between gap-4 border-b p-5"><h2 id={titleId} className="font-semibold">Thẩm định & quyết định hồ sơ</h2><button type="button" disabled={busy} className="fluent-btn-secondary" onClick={() => setOpen(false)} aria-label="Đóng quyết định"><X size={18} /></button></header><div className="p-5">{children}</div></AccessibleDialog></>;
}
