const TOP_INSET_FLOOR_PX = 12;
const TOP_BAR_FLOOR_PX = 48;

/**
 * Top padding for every persistent top bar. The double max guarantees breathing
 * room even when the shell reports a small or zero status-bar inset.
 */
export function topBarPaddingTop(insetTop: number | undefined): number {
  return Math.max(
    Math.max(insetTop ?? 0, TOP_INSET_FLOOR_PX),
    TOP_BAR_FLOOR_PX,
  );
}
