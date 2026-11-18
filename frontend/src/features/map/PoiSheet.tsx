import { journeyDestinationAtom, selectedPoiIdAtom } from "@app/atoms/map";
import { Button } from "@app/components/ui/button";
import { Dialog } from "@app/components/ui/dialog";
import { DEMO_POIS } from "@app/config/demo";
import { sdk } from "@cloudparse/up-miniapps-sdk";
import { useAtomValue, useSetAtom } from "jotai";

export interface PoiSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function PoiSheet({ onOpenChange, open }: PoiSheetProps) {
  const selectedPoiId = useAtomValue(selectedPoiIdAtom);
  const setDestination = useSetAtom(journeyDestinationAtom);
  const poi = DEMO_POIS.find((candidate) => candidate.id === selectedPoiId);

  if (!poi) return null;

  const startJourney = () => {
    setDestination({ coords: [poi.longitude, poi.latitude], name: poi.name });
    sdk.navigation.createJourney({
      destination: [poi.longitude, poi.latitude],
      profile: "walking",
    });
    onOpenChange(false);
  };

  return (
    <Dialog
      description={`${poi.emoji} ${poi.description}`}
      onOpenChange={onOpenChange}
      open={open}
      title={poi.name}
    >
      <Button onClick={startJourney}>Itinéraire à pied</Button>
      <Button onClick={() => onOpenChange(false)} variant="secondary">
        Fermer
      </Button>
    </Dialog>
  );
}
