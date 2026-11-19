"use client";

import React, { useEffect, useRef } from "react";
import { createPortal } from "react-dom";

interface AccessibleDialogProps {
  open: boolean;
  onClose: () => void;
  preventClose?: boolean;
  labelledBy: string;
  describedBy?: string;
  className?: string;
  children: React.ReactNode;
}

const FOCUSABLE_SELECTOR = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled]):not([type='hidden'])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

/**
 * Small shared modal primitive for the prototype and UAT surfaces.
 * It keeps the background inert to keyboard users, moves focus into the
 * dialog, traps Tab/Shift+Tab, closes on Escape and restores the trigger focus.
 */
export function AccessibleDialog({
  open,
  onClose,
  preventClose = false,
  labelledBy,
  describedBy,
  className = "",
  children,
}: AccessibleDialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const overlayRef = useRef<HTMLDivElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);
  const onCloseRef = useRef(onClose);
  const preventCloseRef = useRef(preventClose);

  useEffect(() => {
    onCloseRef.current = onClose;
    preventCloseRef.current = preventClose;
  }, [onClose, preventClose]);

  useEffect(() => {
    if (!open) return;

    previousFocusRef.current = document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null;

    const dialog = dialogRef.current;
    const overlay = overlayRef.current;
    if (!dialog || !overlay) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const background = Array.from(document.body.children)
      .filter((element): element is HTMLElement => element instanceof HTMLElement && element !== overlay)
      .map((element) => ({ element, wasInert: element.inert }));
    background.forEach(({ element }) => { element.inert = true; });

    const getFocusable = () => Array.from(dialog.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR))
      .filter((element) => element.getClientRects().length > 0 && !element.closest("[inert]"));

    const focusable = getFocusable();
    (focusable[0] || dialog).focus();

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        if (!preventCloseRef.current) {
          onCloseRef.current();
        }
        return;
      }

      if (event.key !== "Tab") return;

      const currentFocusable = getFocusable();
      if (currentFocusable.length === 0) {
        event.preventDefault();
        dialog.focus();
        return;
      }

      const first = currentFocusable[0];
      const last = currentFocusable[currentFocusable.length - 1];
      if (!dialog.contains(document.activeElement)) {
        event.preventDefault();
        (event.shiftKey ? last : first).focus();
      } else if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      background.forEach(({ element, wasInert }) => { element.inert = wasInert; });
      document.body.style.overflow = previousOverflow;
      previousFocusRef.current?.focus();
      previousFocusRef.current = null;
    };
  }, [open]);

  if (!open || typeof document === "undefined") return null;

  return createPortal((
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/60 backdrop-blur-sm animate-in fade-in"
      onMouseDown={(event) => {
        if (!preventClose && event.target === event.currentTarget) onClose();
      }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledBy}
        aria-describedby={describedBy}
        tabIndex={-1}
        className={`campus-dialog w-full max-h-[calc(100dvh-2rem)] overflow-y-auto overscroll-contain rounded-2xl border border-slate-200 bg-white text-slate-900 shadow-2xl dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 ${className}`}
      >
        {children}
      </div>
    </div>
  ), document.body);
}
