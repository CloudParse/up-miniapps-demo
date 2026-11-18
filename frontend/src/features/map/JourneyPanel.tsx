import { journeyDestinationAtom } from "@app/atoms/map";
import { Badge } from "@app/components/ui/badge";
import { Button } from "@app/components/ui/button";
import { Card } from "@app/components/ui/card";
import { sdk, useJourney } from "@cloudparse/up-miniapps-sdk";
import { useAtomValue } from "jotai";

// Journey state comes from useJourney(); commands go through sdk.navigation.*.
// The map renders the route itself while a journey is active. Floats over
// the fullscreen map (see MapScreen), so it renders nothing — not even a
// placeholder — until there's an actual destination to show, matching
// by-night's JourneyPanel: a permanent "no itinerary" card floating over
// the map would just be noise.
export function JourneyPanel() {
  const destination = useAtomValue(journeyDestinationAtom);
  const journey = useJourney();

  if (!destination) {
    return null;
  }

  const startPreview = () =>
    sdk.navigation.createJourney({
      destination: destination.coords,
      profile: "walking",
    });

  const modeLabel = journey.mode === "navigation" ? "Guidage actif" : "Aperçu";
  const isArrived = journey.isActive && journey.hasArrived;

  return (
    <Card className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-2">
        <p className="truncate text-sm-plus font-semibold text-ink-bright">
          {destination.name}
        </p>
        {isArrived ? (
          <Badge tone="success">Arrivé</Badge>
        ) : journey.isActive ? (
          <Badge tone="primary">{modeLabel}</Badge>
        ) : (
          <Badge tone="neutral">Inactif</Badge>
        )}
      </div>

      <p className="text-xs-plus text-ink-soft">
        {journey.isCalculating
          ? "Calcul de l'itinéraire…"
          : journey.isActive
            ? `Distance restante : ${journey.distanceRemainingKm.toFixed(2)} km`
            : "Lance un aperçu pour calculer le trajet."}
      </p>
      {journey.error ? (
        <p className="text-xs-plus text-accent-danger">{journey.error}</p>
      ) : null}

      <div className="flex flex-wrap gap-2">
        <Button
          onClick={() => void startPreview()}
          size="sm"
          variant="secondary"
        >
          Aperçu
        </Button>
        <Button
          disabled={!journey.isActive || journey.mode === "navigation"}
          onClick={() => sdk.navigation.start()}
          size="sm"
        >
          Démarrer le guidage
        </Button>
        <Button
          disabled={!journey.isActive}
          onClick={() => sdk.navigation.abort()}
          size="sm"
          variant="danger"
        >
          Arrêter
        </Button>
      </div>
    </Card>
  );
}
