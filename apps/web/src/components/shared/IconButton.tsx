import React from "react";

type Variant = "ghost" | "outline" | "danger" | "primary";

/**
 * A square icon button. The label is both the tooltip and the accessible name, so screen readers and tests still see
 * the same words the old text button had. Use `showLabel` to keep a short visible caption next to the icon.
 */
export function IconButton({ label, icon, variant = "ghost", showLabel = false, className = "", type = "button", ...rest }:
  { label: string; icon: React.ReactNode; variant?: Variant; showLabel?: boolean } & Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, "aria-label" | "title" | "children">) {
  return (
    <button type={type} aria-label={label} title={label} data-variant={variant} data-labelled={showLabel || undefined}
      className={`campus-icon-btn ${className}`} {...rest}>
      <span aria-hidden="true" className="campus-icon-btn-glyph">{icon}</span>
      {showLabel && <span className="campus-icon-btn-label">{label}</span>}
    </button>
  );
}
