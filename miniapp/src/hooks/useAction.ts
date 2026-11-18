import { getErrorMessage } from "@app/lib/errors";
import { useCallback, useState } from "react";

export type ActionState<TResult> =
  | { status: "idle" }
  | { status: "pending" }
  | { status: "success"; result: TResult }
  | { status: "error"; message: string };

// Runs an async SDK or backend call behind a button and keeps its visible state.
export function useAction<TArgs extends unknown[], TResult>(
  action: (...args: TArgs) => Promise<TResult>,
) {
  const [state, setState] = useState<ActionState<TResult>>({ status: "idle" });

  const run = useCallback(
    async (...args: TArgs) => {
      setState({ status: "pending" });
      try {
        const result = await action(...args);
        setState({ result, status: "success" });
        return result;
      } catch (error) {
        setState({ message: getErrorMessage(error), status: "error" });
        return null;
      }
    },
    [action],
  );

  return { run, state };
}
