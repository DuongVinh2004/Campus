import React from "react";
import { AccessibleDialog } from "./AccessibleDialog";

interface ConfirmDialogProps {
  isOpen: boolean;
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  isDestructive?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  isOpen,
  title,
  description,
  confirmLabel = "Xác nhận",
  cancelLabel = "Hủy",
  isDestructive = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  if (!isOpen) return null;

  return (
    <AccessibleDialog
      open={isOpen}
      onClose={onCancel}
      labelledBy="dialog-title"
      describedBy="dialog-description"
      className="relative bg-[var(--surface-card)] text-[var(--text-primary)] border border-[var(--border-color)] rounded-xl p-6 w-full max-w-sm shadow-lg animate-in fade-in zoom-in-95"
    >
      <h3 id="dialog-title" className="text-lg font-semibold text-[var(--text-primary)] mb-2">
          {title}
      </h3>
      <p id="dialog-description" className="text-sm text-[var(--text-secondary)] mb-6">
          {description}
      </p>

      <div className="flex items-center justify-end gap-3">
        <button
          type="button"
          onClick={onCancel}
          className="fluent-btn-secondary"
        >
          {cancelLabel}
        </button>
        <button
          type="button"
          onClick={onConfirm}
          className={
            isDestructive
              ? "btn-danger rounded-lg px-4 py-2 text-sm font-medium transition-colors"
              : "fluent-btn-primary"
          }
        >
          {confirmLabel}
        </button>
      </div>
    </AccessibleDialog>
  );
}
