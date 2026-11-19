"use client";

import React, {
  createContext,
  useContext,
  useState,
  useCallback,
  type ReactNode,
} from "react";

export type ToastType = "success" | "error" | "warning" | "info";

export interface Toast {
  id: string;
  message: string;
  type: ToastType;
  duration?: number;
}

interface ToastContextType {
  toasts: Toast[];
  addToast: (message: string, type?: ToastType, duration?: number) => void;
  removeToast: (id: string) => void;
}

const ToastContext = createContext<ToastContextType>({
  toasts: [],
  addToast: () => {},
  removeToast: () => {},
});

export function useToast() {
  return useContext(ToastContext);
}

const TOAST_ICONS: Record<ToastType, string> = {
  success: "✓",
  error: "✕",
  warning: "⚠",
  info: "ℹ",
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const addToast = useCallback(
    (message: string, type: ToastType = "success", duration = 4000) => {
      const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
      setToasts((prev) => [...prev, { id, message, type, duration }]);

      if (duration > 0) {
        setTimeout(() => {
          removeToast(id);
        }, duration);
      }
    },
    [removeToast]
  );

  return (
    <ToastContext.Provider value={{ toasts, addToast, removeToast }}>
      {children}

      {/* Toast Container */}
      {toasts.length > 0 && (
        <div
          className="toast-container"
          role="region"
          aria-label="Thông báo hệ thống"
          aria-live="polite"
        >
          {toasts.map((toast) => (
            <div
              key={toast.id}
              className={`toast-item toast-${toast.type}`}
              role="status"
            >
              <span style={{ fontSize: "16px", flexShrink: 0 }}>
                {TOAST_ICONS[toast.type]}
              </span>
              <details style={{ flex: 1, minWidth: 0 }}>
                <summary className="cursor-pointer truncate" title={toast.message}>{toast.message}</summary>
                <p className="mt-1 max-h-32 overflow-y-auto whitespace-pre-wrap break-words font-normal">{toast.message}</p>
              </details>
              <button
                type="button"
                onClick={() => removeToast(toast.id)}
                style={{
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  color: "inherit",
                  padding: "4px",
                  fontSize: "14px",
                  opacity: 0.7,
                  minHeight: "24px",
                  minWidth: "24px",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
                aria-label="Đóng thông báo"
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      )}
    </ToastContext.Provider>
  );
}
