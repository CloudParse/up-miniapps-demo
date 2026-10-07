export interface EndpointBadgeProps {
  method: string;
  path: string;
}

export function EndpointBadge({ method, path }: EndpointBadgeProps) {
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-brand-border bg-brand-card-strong/60 px-3 py-1 font-mono text-xs-plus text-ink-soft">
      <span className="font-semibold text-accent-success">{method}</span>
      {path}
    </span>
  );
}
