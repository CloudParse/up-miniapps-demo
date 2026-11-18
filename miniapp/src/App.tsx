import { profileAtom } from "@app/atoms/account";
import { bootAtom } from "@app/atoms/boot";
import { contextAtom, isDarkAtom } from "@app/atoms/context";
import { appendEventAtom } from "@app/atoms/eventLog";
import {
  activeTabAtom,
  overlayAtom,
  toolsPageAtom,
} from "@app/atoms/navigation";
import { AppShell } from "@app/components/layout/AppShell";
import { BottomNav } from "@app/components/layout/BottomNav";
import { ErrorScreen } from "@app/components/layout/ErrorScreen";
import { ExitButton } from "@app/components/layout/ExitButton";
import { SplashScreen } from "@app/components/layout/SplashScreen";
import { TopBar } from "@app/components/layout/TopBar";
import { APP_CONFIG } from "@app/config/env";
import { TABS, type TabId } from "@app/config/tabs";
import { DevUserPicker } from "@app/dev/DevUserPicker";
import { useDevSession } from "@app/dev/useDevSession";
import { AccountScreen } from "@app/features/account/AccountScreen";
import { HomeScreen } from "@app/features/home/HomeScreen";
import { MapScreen } from "@app/features/map/MapScreen";
import { MediaScreen } from "@app/features/media/MediaScreen";
import { ToolsScreen } from "@app/features/tools/ToolsScreen";
import { useSdkEvent } from "@app/hooks/useSdkEvent";
import { getErrorMessage } from "@app/lib/errors";
import { appStore } from "@app/lib/store";
import { mergeShellContext } from "@app/services/shellContext";
import {
  ExitConfirmModal,
  GlobalEvent,
  type IContextState,
  SDKProvider,
  sdk,
  UIEvent,
} from "@cloudparse/up-miniapps-sdk";
import { useAtom, useAtomValue, useSetAtom } from "jotai";
import { useCallback, useEffect } from "react";

const TAB_TITLES = Object.fromEntries(
  TABS.map((tab) => [tab.id, tab.label]),
) as Record<TabId, string>;

// This app's own theme choice, passed to sdk.initialize({isDark}) and also
// recorded into contextAtom right after (see bootApp) — the single source
// of truth for both. No in-app toggle exists yet; flip this to exercise the
// light theme (including the map's own light style variant) during dev.
const INITIAL_IS_DARK = true;

// The back gesture and the top-left button share one order: the most specific
// open state closes first, and the exit confirmation is the last resort.
function handleBack() {
  const overlay = appStore.get(overlayAtom);
  if (overlay.kind !== "none") {
    appStore.set(overlayAtom, { kind: "none" });
    return;
  }
  if (appStore.get(toolsPageAtom) !== "index") {
    appStore.set(toolsPageAtom, "index");
    return;
  }
  if (appStore.get(activeTabAtom) !== "home") {
    appStore.set(activeTabAtom, "home");
    return;
  }
  appStore.set(overlayAtom, { kind: "exit" });
}

// Development without VITE_DEV_TOKEN: sign in as a test user of the DEV backend.
const USE_DEV_USERS = APP_CONFIG.isDev && APP_CONFIG.devToken === "";

export default function App() {
  const devSession = useDevSession(USE_DEV_USERS);
  const signedIn = !USE_DEV_USERS || devSession.token !== "";
  return (
    <SDKProvider
      debug={false}
      edgeToEdge
      mockJWTToken={USE_DEV_USERS ? devSession.token : APP_CONFIG.devToken}
    >
      {signedIn ? (
        <DemoApp />
      ) : (
        <DevUserPicker
          error={devSession.error}
          onPick={devSession.signIn}
          pending={devSession.user}
        />
      )}
    </SDKProvider>
  );
}

function DemoApp() {
  const [context, setContext] = useAtom(contextAtom);
  const [bootState, setBootState] = useAtom(bootAtom);
  const isDark = useAtomValue(isDarkAtom);
  const [activeTab, setActiveTab] = useAtom(activeTabAtom);
  const [toolsPage] = useAtom(toolsPageAtom);
  const [overlay, setOverlay] = useAtom(overlayAtom);
  const setProfile = useSetAtom(profileAtom);
  const appendEvent = useSetAtom(appendEventAtom);

  // isDark goes into initialize() itself: a separate updateContext() after it
  // would show the host's own theme for a whole extra round-trip.
  const bootApp = useCallback(async () => {
    setBootState({ phase: "loading" });
    try {
      const response = await sdk.initialize({ isDark: INITIAL_IS_DARK });
      // Direct OSRM backend for sdk.routing.getRoute()/useJourney (the
      // journey-preview demo on the Map tab) — without this, getRoute()
      // falls back to the host bridge, which the dev-mode BridgeMocker
      // simulator doesn't mock, so the journey demo would silently show no
      // route. Same config the other apps with a routing feature use
      // (by-night, toilets — confirmed via their own App.tsx; cursor and
      // explore have no journey/routing feature, so they don't set this).
      sdk.config({
        routingBackend: {
          backend: "osrm",
          baseUrl: "https://osrm.cloudparse.fr",
        },
      });
      setContext((previous: IContextState) =>
        mergeShellContext(previous, {
          env: response.env,
          insets: response.insets,
          // isDark isn't echoed back on IInitializationResponse — it's a
          // request-only field (the app's own theme choice, never
          // negotiated by the host) — so the same value just passed to
          // initialize() has to be recorded here explicitly, or isDarkAtom
          // (derived from contextAtom.isDark) never sees anything but its
          // own hardcoded fallback, and this app's light theme — including
          // the local map style's own light variant — stays unreachable no
          // matter what's requested above.
          isDark: INITIAL_IS_DARK,
        }),
      );
      if (response.profile) {
        setProfile({ data: response.profile, status: "ready" });
      }
      appendEvent({ label: `INITIALIZE ${response.name}`, source: "app" });
      setBootState({ phase: "ready" });
    } catch (error) {
      setBootState({ message: getErrorMessage(error), phase: "error" });
    }
  }, [appendEvent, setBootState, setContext, setProfile]);

  useEffect(() => {
    void bootApp();
  }, [bootApp]);

  useEffect(() => {
    document.documentElement.dataset.theme = isDark ? "dark" : "light";
  }, [isDark]);

  useSdkEvent<unknown>(GlobalEvent.UPDATE_CONTEXT, (data) => {
    setContext((previous: IContextState) => mergeShellContext(previous, data));
    appendEvent({ label: "UPDATE_CONTEXT", source: "shell" });
  });

  useSdkEvent<unknown>(UIEvent.BACK_GESTURE, () => {
    appendEvent({ label: "BACK_GESTURE", source: "shell" });
    handleBack();
  });

  if (bootState.phase === "loading") {
    return <SplashScreen />;
  }

  if (bootState.phase === "error") {
    return (
      <ErrorScreen
        insetTop={context.insets.top}
        message={bootState.message}
        onExit={() => setOverlay({ kind: "exit" })}
        onRetry={() => void bootApp()}
      />
    );
  }

  const isSubPage = activeTab === "tools" && toolsPage !== "index";

  const handleLeading = () => {
    if (isSubPage) {
      appStore.set(toolsPageAtom, "index");
      return;
    }
    setOverlay({ kind: "exit" });
  };

  const handleQuit = () => {
    setOverlay({ kind: "none" });
    void sdk.ui.exit();
  };

  return (
    <AppShell insets={context.insets}>
      {/* MapScreen renders its own floating TopBar (by-night/explore
          pattern: the map is the whole screen, chrome floats on top of it)
          so its own container isn't shrunk by a push-down header here. */}
      {activeTab === "map" ? null : (
        <TopBar
          insetTop={context.insets.top}
          leading={
            <ExitButton
              mode={isSubPage ? "back" : "exit"}
              onPress={handleLeading}
            />
          }
          title={isSubPage ? "Outils" : TAB_TITLES[activeTab]}
        />
      )}
      <main className="flex min-h-0 flex-1 flex-col">
        {activeTab === "home" ? <HomeScreen /> : null}
        {activeTab === "map" ? <MapScreen /> : null}
        {activeTab === "tools" ? <ToolsScreen /> : null}
        {activeTab === "media" ? <MediaScreen /> : null}
        {activeTab === "account" ? <AccountScreen /> : null}
      </main>
      <BottomNav
        activeTab={activeTab}
        insetBottom={context.insets.bottom}
        onSelect={(tab) => {
          setActiveTab(tab);
          void sdk.updateContext({ demoLastTab: tab });
        }}
      />
      <ExitConfirmModal
        appName={APP_CONFIG.appName}
        isOpen={overlay.kind === "exit"}
        onClose={() => setOverlay({ kind: "none" })}
        onConfirm={handleQuit}
      />
    </AppShell>
  );
}
