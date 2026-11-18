import { BackButtonControl } from "@cloudparse/up-miniapps-sdk";

export interface ExitButtonProps {
  mode: "exit" | "back";
  onPress: () => void;
}

// One shared top-left control: LogOut quits the mini-app (through the confirm
// modal), ChevronLeft steps back inside it. Used by the top bar and the error
// screen so the two can never drift apart. Thin wrapper around the SDK's own
// `BackButtonControl` (bare, unpositioned — this app's `TopBar` owns the
// actual fixed/inset positioning, so the SDK's full `ExitButton` wrapper,
// which carries its own fixed header, doesn't fit here) — translates this
// app's `mode` string into the SDK component's `isExitAction` boolean. Was a
// hand-rolled button before; delegating here means this app exercises the
// SDK's own component instead of duplicating it, same reasoning as the
// ExitConfirmModal migration in App.tsx.
export function ExitButton({ mode, onPress }: ExitButtonProps) {
  return <BackButtonControl isExitAction={mode === "exit"} onPress={onPress} />;
}
