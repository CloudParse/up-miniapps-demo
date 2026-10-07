import { BackButtonControl } from "@cloudparse/up-miniapps-sdk";

export interface ExitButtonProps {
  mode: "exit" | "back";
  onPress: () => void;
}

// Thin wrapper over the SDK's BackButtonControl: maps `mode` to `isExitAction`.
// Shared by the top bar and the error screen so they cannot drift apart.
export function ExitButton({ mode, onPress }: ExitButtonProps) {
  return <BackButtonControl isExitAction={mode === "exit"} onPress={onPress} />;
}
