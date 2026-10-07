import { type ClassValue, clsx } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

// twMerge does not know the app's custom @theme tokens, so `text-md-plus` and
// `text-ink-bright` in the same className would silently drop one another.
// Registering them here keeps cn() correct for every component.
const twMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      "font-size": [
        "text-xs-plus",
        "text-sm-plus",
        "text-md-plus",
        "text-xl-plus",
        "text-display",
      ],
    },
    theme: {
      color: [
        "brand-bg",
        "brand-card",
        "brand-card-strong",
        "brand-border",
        "brand-panel",
        "accent-primary",
        "accent-secondary",
        "accent-success",
        "accent-danger",
        "ink-bright",
        "ink-soft",
        "ink-faint",
        "ink-on-accent",
        "ink-deep",
      ],
    },
  },
  override: {
    conflictingClassGroups: { "font-size": [] },
  },
});

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
