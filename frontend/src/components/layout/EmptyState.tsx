import type { ReactNode } from "react";

export interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
}

export function EmptyState({
  action,
  description,
  icon,
  title,
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-3xl border border-dashed border-brand-border px-5 py-8 text-center">
      {icon ? <div className="text-ink-faint">{icon}</div> : null}
      <p className="text-sm-plus font-medium text-ink-bright">{title}</p>
      {description ? (
        <p className="text-xs-plus text-ink-soft">{description}</p>
      ) : null}
      {action}
    </div>
  );
}
