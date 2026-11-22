import { balanceAtom, profileAtom } from "@app/atoms/account";
import { contextAtom } from "@app/atoms/context";
import { activeTabAtom } from "@app/atoms/navigation";
import { EmptyState } from "@app/components/layout/EmptyState";
import { ScreenTitle } from "@app/components/layout/ScreenTitle";
import { Badge } from "@app/components/ui/badge";
import { Button } from "@app/components/ui/button";
import { Card } from "@app/components/ui/card";
import { SkeletonBlock } from "@app/components/ui/skeleton";
import { FEATURE_HIGHLIGHTS } from "@app/config/demo";
import type { TabId } from "@app/config/tabs";
import {
  loadBalance,
  loadProfile,
  refreshAccount,
} from "@app/features/account/accountLoaders";
import { BackendGreetingCard } from "@app/features/home/BackendGreetingCard";
import { DemoDataCard } from "@app/features/home/DemoDataCard";
import { loadGreeting } from "@app/features/home/greetingLoader";
import { getBackendUrl } from "@app/services/backend";
import {
  PullToRefresh,
  SwipeCarousel,
  type SwipeCarouselItem,
} from "@cloudparse/up-miniapps-sdk";
import { useAtomValue, useSetAtom } from "jotai";
import { useEffect, useMemo, useState } from "react";

interface HighlightSlide extends SwipeCarouselItem {
  tab: TabId;
}

async function refreshHome(): Promise<void> {
  await Promise.all([
    refreshAccount(),
    getBackendUrl() ? loadGreeting(true) : Promise.resolve(),
  ]);
}

export function HomeScreen() {
  const profile = useAtomValue(profileAtom);
  const balance = useAtomValue(balanceAtom);
  const context = useAtomValue(contextAtom);
  const setActiveTab = useSetAtom(activeTabAtom);
  const backendUrl = getBackendUrl();
  const [activeSlide, setActiveSlide] = useState<string>(
    FEATURE_HIGHLIGHTS[0]?.id ?? "",
  );

  useEffect(() => {
    void loadProfile();
    void loadBalance();
  }, []);

  const slides = useMemo<HighlightSlide[]>(
    () =>
      FEATURE_HIGHLIGHTS.map((highlight) => ({
        content: (
          <Card className="flex h-full flex-col gap-3">
            <p className="font-display text-md-plus font-semibold text-ink-bright">
              {highlight.title}
            </p>
            <p className="text-sm-plus text-ink-soft">
              {highlight.description}
            </p>
            <div className="mt-auto">
              <Button
                onClick={() => setActiveTab(highlight.tab)}
                size="sm"
                variant="secondary"
              >
                Ouvrir
              </Button>
            </div>
          </Card>
        ),
        id: highlight.id,
        tab: highlight.tab,
      })),
    [setActiveTab],
  );

  const greetingName =
    profile.status === "ready"
      ? (profile.data.firstName ?? profile.data.fullName)
      : null;

  return (
    <PullToRefresh
      className="flex-1 min-h-0 overflow-y-auto"
      onRefresh={refreshHome}
    >
      <div className="flex flex-col gap-4 px-4 pt-1 pb-6">
        <ScreenTitle
          subtitle="Tire vers le bas pour actualiser ton compte."
          title={greetingName ? `Bonjour ${greetingName}` : "Bienvenue"}
        />

        <Card className="flex items-center justify-between gap-3" tone="strong">
          <div>
            <p className="text-xs-plus font-medium uppercase text-ink-faint">
              Solde fidélité
            </p>
            {balance.status === "ready" ? (
              <p className="text-xl-plus font-semibold text-ink-bright">
                {balance.data.balance.toLocaleString("fr-FR")}{" "}
                {balance.data.currency}
              </p>
            ) : balance.status === "error" ? (
              <p className="text-xs-plus text-accent-danger">
                {balance.message}
              </p>
            ) : (
              <SkeletonBlock className="mt-1 h-6 w-28" />
            )}
          </div>
          <Badge tone={backendUrl ? "success" : "warning"}>
            {backendUrl ? "Backend connecté" : "Backend absent"}
          </Badge>
        </Card>

        {backendUrl ? (
          <>
            <BackendGreetingCard />
            <DemoDataCard />
          </>
        ) : (
          <EmptyState
            description="Renseigne VITE_BACKEND_URL dans .env, ou laisse le shell fournir env.backendUrl. Aucune URL n'est devinée."
            title="Backend non configuré"
          />
        )}

        <div className="flex flex-col gap-2">
          <p className="font-display text-md-plus font-semibold text-ink-bright">
            À la une
          </p>
          <SwipeCarousel
            activeId={activeSlide}
            items={slides}
            onActiveChange={setActiveSlide}
          />
        </div>

        <Card className="flex flex-col gap-2 text-xs-plus text-ink-soft">
          <p className="font-medium text-ink-bright">Contexte shell</p>
          <p>
            Insets — haut {context.insets.top}, bas {context.insets.bottom},
            gauche {context.insets.left}, droite {context.insets.right}
          </p>
          <p>Variables env reçues : {Object.keys(context.env ?? {}).length}</p>
        </Card>
      </div>
    </PullToRefresh>
  );
}
