import React from "react";
import { FileQuestion, type LucideIcon } from "lucide-react";

interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description: string;
  action?: React.ReactNode;
}

export function EmptyState({ icon: Icon = FileQuestion, title, description, action }: EmptyStateProps) {
  return (
    <div className="campus-empty-state border border-dashed border-[var(--border-color)]">
      <Icon aria-hidden="true" />
      <h3 className="text-base font-semibold text-[var(--text-primary)]">{title}</h3>
      <p className="max-w-sm">{description}</p>
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}
