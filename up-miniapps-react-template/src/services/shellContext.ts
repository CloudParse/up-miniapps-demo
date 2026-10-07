import type { IContextState } from "@cloudparse/up-miniapps-sdk";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

// UPDATE_CONTEXT is a partial push: merge it, never replace the whole container,
// or fields like insets and env would silently disappear.
export function mergeShellContext(
  previous: IContextState,
  update: unknown,
): IContextState {
  if (!isRecord(update)) return previous;
  const insets = isRecord(update.insets)
    ? { ...previous.insets, ...update.insets }
    : previous.insets;
  return { ...previous, ...update, insets };
}
