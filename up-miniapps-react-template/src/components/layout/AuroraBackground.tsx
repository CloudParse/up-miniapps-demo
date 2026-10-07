// Purely decorative: two blurred gradient orbs drifting behind the content.
// Colors come from theme tokens so a rebrand only touches styles/index.css.
export function AuroraBackground() {
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 overflow-hidden"
    >
      <div className="absolute -left-1/4 -top-1/6 size-aurora animate-drift rounded-full bg-accent-primary/25 blur-aurora" />
      <div className="absolute -bottom-1/6 -right-1/4 size-aurora-wide animate-drift-slow rounded-full bg-accent-secondary/25 blur-aurora-wide" />
    </div>
  );
}
