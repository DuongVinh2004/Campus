"use client";

import { useId, useRef } from "react";
import { EllipsisVertical } from "lucide-react";

/** Native popover keeps actions above the scrolling list and handles outside clicks. */
export function HistoryActions({ label, disabled, actions }: {
  label: string;
  disabled?: boolean;
  actions: { label: string; run: () => void }[];
}) {
  const id = useId();
  const popup = useRef<HTMLDivElement>(null);
  return <>
    <button type="button" aria-label={label} title={label} disabled={disabled}
      popoverTarget={id} style={{ minWidth: 28, minHeight: 28 }} className="campus-overflow-trigger inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-200 dark:hover:bg-slate-700"
      onClick={event => {
        const rect = event.currentTarget.getBoundingClientRect();
        const height = actions.length * 40 + 12;
        if (popup.current) Object.assign(popup.current.style, {
          left: `${Math.max(8, Math.min(rect.right - 208, window.innerWidth - 216))}px`,
          top: `${Math.max(8, rect.bottom + height > window.innerHeight ? rect.top - height : rect.bottom + 4)}px`,
        });
      }}><EllipsisVertical aria-hidden="true" className="h-4 w-4" /></button>
    <div id={id} ref={popup} popover="auto" aria-label={label}
      className="fixed m-0 w-52 rounded-xl border border-slate-200 bg-white p-1.5 text-sm text-slate-900 shadow-xl dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
      onKeyDown={event => { if (event.key === "Escape") event.stopPropagation(); }}>
      {actions.map(action => <button key={action.label} type="button"
        className="flex h-10 w-full items-center rounded-lg px-3 text-left hover:bg-slate-100 dark:hover:bg-slate-800"
        onClick={() => { popup.current?.hidePopover(); action.run(); }}>{action.label}</button>)}
    </div>
  </>;
}
