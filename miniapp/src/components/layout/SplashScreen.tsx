import logoUrl from "@app/assets/logo.svg";
import { SkeletonBlock } from "@app/components/ui/skeleton";

export function SplashScreen() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-6 bg-brand-bg px-8 text-ink-bright">
      <img
        alt="Up Demo"
        className="h-20 w-20 rounded-3xl border border-accent-primary/20"
        src={logoUrl}
      />
      <div className="text-center">
        <p className="font-display text-xl-plus font-semibold">Up Demo</p>
        <p className="mt-1 text-sm-plus text-ink-faint">
          Chargement de la mini-app…
        </p>
      </div>
      <SkeletonBlock className="h-2 w-40" />
    </div>
  );
}
