import { TABS, type TabId } from "@app/config/tabs";
import { cn } from "@app/lib/utils";

// The nav bar's own background must extend behind the (transparent)
// simulated/real system nav bar, not stop at the tab row — see AppShell's
// own comment for why this lives here (padding) instead of as a gap on
// the root. `BOTTOM_PADDING_BASE_PX` is the bar's normal breathing room
// below the tab icons; `insetBottom` grows the box further so its
// background, not AppShell's, shows behind the system bar.
const BOTTOM_PADDING_BASE_PX = 8;

export interface BottomNavProps {
  activeTab: TabId;
  onSelect: (tab: TabId) => void;
  insetBottom: number;
}

export function BottomNav({
  activeTab,
  insetBottom,
  onSelect,
}: BottomNavProps) {
  return (
    <nav
      className="grid shrink-0 grid-cols-5 border-t border-brand-border bg-brand-nav-bg px-2 pt-2"
      style={{ paddingBottom: BOTTOM_PADDING_BASE_PX + (insetBottom || 0) }}
    >
      {TABS.map((tab) => {
        const Icon = tab.icon;
        const isActive = tab.id === activeTab;
        return (
          <button
            aria-current={isActive ? "page" : undefined}
            className={cn(
              "flex min-h-11 flex-col items-center justify-center gap-1 rounded-2xl text-xxs-minus font-medium transition-colors",
              isActive ? "text-accent-primary" : "text-ink-faint",
            )}
            key={tab.id}
            onClick={() => onSelect(tab.id)}
            type="button"
          >
            <Icon size={22} strokeWidth={isActive ? 2.2 : 1.8} />
            <span>{tab.label}</span>
          </button>
        );
      })}
    </nav>
  );
}
