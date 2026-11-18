import { ScreenTitle } from "@app/components/layout/ScreenTitle";
import { ConfirmModal } from "@app/components/modals/ConfirmModal";
import { Button } from "@app/components/ui/button";
import { Card } from "@app/components/ui/card";
import { SegmentedControl } from "@app/components/ui/segmented-control";
import { Switch } from "@app/components/ui/switch";
import {
  PullToRefresh,
  SwipeCarousel,
  type SwipeCarouselItem,
  sdk,
} from "@cloudparse/up-miniapps-sdk";
import { useState } from "react";

const CAROUSEL_ITEMS: SwipeCarouselItem[] = [
  {
    content: (
      <Card className="h-full text-sm-plus text-ink-bright">
        Premier panneau
      </Card>
    ),
    id: "one",
  },
  {
    content: (
      <Card className="h-full text-sm-plus text-ink-bright">
        Deuxième panneau
      </Card>
    ),
    id: "two",
  },
  {
    content: (
      <Card className="h-full text-sm-plus text-ink-bright">
        Troisième panneau
      </Card>
    ),
    id: "three",
  },
];

type Density = "compact" | "comfortable";

const PULL_ROWS = Array.from({ length: 12 }, (_, n) => `Ligne ${n + 1}`);

export function UiKitDemo() {
  const [activeSlide, setActiveSlide] = useState("one");
  const [refreshCount, setRefreshCount] = useState(0);
  const [density, setDensity] = useState<Density>("comfortable");
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [hideStatusBar, setHideStatusBar] = useState(false);
  const [hideNavigationBar, setHideNavigationBar] = useState(false);

  return (
    <div className="flex flex-col gap-5">
      <ScreenTitle
        subtitle="Composants d'interface fournis par le SDK et le kit de la mini-app."
        title="Interface"
      />

      <section className="flex flex-col gap-2">
        <p className="font-display text-md-plus font-semibold text-ink-bright">
          Carrousel
        </p>
        <SwipeCarousel
          activeId={activeSlide}
          items={CAROUSEL_ITEMS}
          onActiveChange={setActiveSlide}
        />
      </section>

      <section className="flex flex-col gap-2">
        <p className="font-display text-md-plus font-semibold text-ink-bright">
          Tirer pour actualiser
        </p>
        <PullToRefresh
          className="h-64 overflow-y-auto"
          onRefresh={async () => {
            await new Promise((resolve) => setTimeout(resolve, 800));
            setRefreshCount((count) => count + 1);
          }}
        >
          <div className="flex flex-col gap-2 p-1">
            {PULL_ROWS.map((row) => (
              <Card className="p-3 text-sm-plus text-ink-soft" key={row}>
                {row} — actualisations : {refreshCount}
              </Card>
            ))}
          </div>
        </PullToRefresh>
      </section>

      <section className="flex flex-col gap-2">
        <p className="font-display text-md-plus font-semibold text-ink-bright">
          Sélecteur segmenté
        </p>
        <SegmentedControl
          onChange={setDensity}
          options={[
            { label: "Confort", value: "comfortable" },
            { label: "Compact", value: "compact" },
          ]}
          value={density}
        />
        <p className="text-xs-plus text-ink-soft">
          Densité choisie : {density}
        </p>
      </section>

      <section className="flex flex-col gap-2">
        <p className="font-display text-md-plus font-semibold text-ink-bright">
          Modale de confirmation
        </p>
        <Button onClick={() => setIsDialogOpen(true)} variant="outline">
          Ouvrir la modale
        </Button>
        <ConfirmModal
          confirmLabel="Compris"
          description="Une modale dédiée remplace window.confirm, jamais rendue par le navigateur."
          onCancel={() => setIsDialogOpen(false)}
          onConfirm={() => setIsDialogOpen(false)}
          open={isDialogOpen}
          title="Exemple de confirmation"
        />
      </section>

      <section className="flex flex-col gap-3">
        <p className="font-display text-md-plus font-semibold text-ink-bright">
          Barres système
        </p>
        <Card className="flex items-center justify-between gap-3">
          <span className="text-sm-plus text-ink-bright">
            Masquer la barre d'état
          </span>
          <Switch
            aria-label="Masquer la barre d'état"
            checked={hideStatusBar}
            onCheckedChange={(checked) => {
              setHideStatusBar(checked);
              void sdk.ui.setSystemBarsHidden({ statusBar: checked });
            }}
          />
        </Card>
        <Card className="flex items-center justify-between gap-3">
          <span className="text-sm-plus text-ink-bright">
            Masquer la barre de navigation
          </span>
          <Switch
            aria-label="Masquer la barre de navigation"
            checked={hideNavigationBar}
            onCheckedChange={(checked) => {
              setHideNavigationBar(checked);
              void sdk.ui.setSystemBarsHidden({ navigationBar: checked });
            }}
          />
        </Card>
        <p className="text-xs-plus text-ink-faint">
          Le shell n'autorise jamais à masquer une barre pendant un écran de
          sécurité.
        </p>
      </section>

      <section className="flex flex-col gap-2">
        <p className="font-display text-md-plus font-semibold text-ink-bright">
          Défilement natif
        </p>
        <div className="grid grid-cols-2 gap-2">
          <Button
            onClick={() =>
              void sdk.ui.setScrollConfig({ topScrollMore: { enabled: true } })
            }
            size="sm"
            variant="secondary"
          >
            Activer
          </Button>
          <Button
            onClick={() =>
              void sdk.ui.setScrollConfig({ topScrollMore: { enabled: false } })
            }
            size="sm"
            variant="outline"
          >
            Désactiver
          </Button>
        </div>
      </section>
    </div>
  );
}
