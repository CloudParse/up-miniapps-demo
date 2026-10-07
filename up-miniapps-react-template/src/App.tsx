import { bootAtom } from "@app/atoms/boot";
import { contextAtom } from "@app/atoms/context";
import { overlayAtom } from "@app/atoms/navigation";
import { AppShell } from "@app/components/layout/AppShell";
import { ErrorScreen } from "@app/components/layout/ErrorScreen";
import { ExitButton } from "@app/components/layout/ExitButton";
import { SplashScreen } from "@app/components/layout/SplashScreen";
import { TopBar } from "@app/components/layout/TopBar";
import { ExitConfirmModal } from "@app/components/modals/ExitConfirmModal";
import { APP_CONFIG } from "@app/config/env";
import { HelloScreen } from "@app/features/hello/HelloScreen";
import { useBootstrap } from "@app/hooks/useBootstrap";
import { useSdkEvent } from "@app/hooks/useSdkEvent";
import { appStore } from "@app/lib/store";
import { mergeShellContext } from "@app/services/shellContext";
import {
  GlobalEvent,
  type IContextState,
  SDKProvider,
  sdk,
  UIEvent,
} from "@cloudparse/up-miniapps-sdk";
import { useAtom, useAtomValue } from "jotai";

// The back gesture and the top-left button share one ladder: the most specific
// open state closes first, the exit confirmation is the last resort.
function handleBack() {
  if (appStore.get(overlayAtom).kind !== "none") {
    appStore.set(overlayAtom, { kind: "none" });
    return;
  }
  appStore.set(overlayAtom, { kind: "exit" });
}

export default function App() {
  return (
    <SDKProvider debug={false} mockJWTToken={APP_CONFIG.devToken}>
      <MiniApp />
    </SDKProvider>
  );
}

function MiniApp() {
  const [context, setContext] = useAtom(contextAtom);
  const bootState = useAtomValue(bootAtom);
  const [overlay, setOverlay] = useAtom(overlayAtom);

  const bootApp = useBootstrap();

  useSdkEvent<unknown>(GlobalEvent.UPDATE_CONTEXT, (data) => {
    setContext((previous: IContextState) => mergeShellContext(previous, data));
  });

  useSdkEvent<unknown>(UIEvent.BACK_GESTURE, handleBack);

  const requestExit = () => setOverlay({ kind: "exit" });

  if (bootState.phase === "loading") {
    return <SplashScreen />;
  }

  if (bootState.phase === "error") {
    return (
      <ErrorScreen
        insetTop={context.insets.top}
        message={bootState.message}
        onExit={requestExit}
        onRetry={() => void bootApp()}
      />
    );
  }

  return (
    <AppShell insets={context.insets}>
      <TopBar
        insetTop={context.insets.top}
        leading={<ExitButton mode="exit" onPress={requestExit} />}
        title={APP_CONFIG.appName}
      />
      <main className="flex min-h-0 flex-1 flex-col">
        <HelloScreen />
      </main>
      <ExitConfirmModal
        onCancel={() => setOverlay({ kind: "none" })}
        onConfirm={() => {
          setOverlay({ kind: "none" });
          void sdk.ui.exit();
        }}
        open={overlay.kind === "exit"}
      />
    </AppShell>
  );
}
