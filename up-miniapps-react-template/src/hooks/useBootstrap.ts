import { bootAtom } from "@app/atoms/boot";
import { contextAtom } from "@app/atoms/context";
import { getErrorMessage } from "@app/lib/errors";
import { mergeShellContext } from "@app/services/shellContext";
import { type IContextState, sdk } from "@cloudparse/up-miniapps-sdk";
import { useSetAtom } from "jotai";
import { useCallback, useEffect } from "react";

// Runs the SDK handshake once on mount and returns `retry` for the error screen.
export function useBootstrap(): () => Promise<void> {
  const setBoot = useSetAtom(bootAtom);
  const setContext = useSetAtom(contextAtom);

  const bootstrap = useCallback(async () => {
    setBoot({ phase: "loading" });
    try {
      // `isDark` goes into initialize() itself: a later updateContext() would
      // show the host's own theme for an extra round-trip.
      const response = await sdk.initialize({ isDark: true });
      setContext((previous: IContextState) =>
        mergeShellContext(previous, {
          env: response.env,
          insets: response.insets,
        }),
      );
      setBoot({ phase: "ready" });
    } catch (error) {
      setBoot({ message: getErrorMessage(error), phase: "error" });
    }
  }, [setBoot, setContext]);

  useEffect(() => {
    void bootstrap();
  }, [bootstrap]);

  return bootstrap;
}
