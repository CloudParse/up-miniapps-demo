const TOP_BAR_FLOOR_PX = 48;

/**
 * Top padding for every persistent top bar: the status-bar inset reported by
 * the shell, never less than a comfortable minimum (the shell may report 0).
 */
export function topBarPaddingTop(insetTop: number | undefined): number {
  return Math.max(insetTop ?? 0, TOP_BAR_FLOOR_PX);
}
