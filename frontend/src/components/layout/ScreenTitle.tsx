export interface ScreenTitleProps {
  title: string;
  subtitle?: string;
}

export function ScreenTitle({ subtitle, title }: ScreenTitleProps) {
  return (
    <div className="mb-4">
      <h1 className="font-display text-2xl-plus font-semibold text-ink-bright">
        {title}
      </h1>
      {subtitle ? (
        <p className="mt-1 text-sm-plus text-ink-soft">{subtitle}</p>
      ) : null}
    </div>
  );
}
