import { geofenceDemoOpenAtom, selectedPoiIdAtom } from "@app/atoms/map";
import { Button } from "@app/components/ui/button";
import { ANNECY_CENTER, DEMO_POIS } from "@app/config/demo";
import {
  CompassRecenterStack,
  useMapControls,
} from "@cloudparse/up-miniapps-sdk";
import { useAtomValue, useSetAtom } from "jotai";
import { useEffect } from "react";

export interface MapToolbarProps {
  /**
   * Distance from the map's own top edge (the map is fullscreen, under the
   * status bar and MapScreen's floating header) to where this row starts —
   * must clear that floating header, computed by MapScreen.
   */
  topOffset: number;
  /**
   * Distance from the phone screen's bottom edge to where
   * CompassRecenterStack starts — must clear BottomNav (always rendered,
   * even on this tab) plus its own safe-area inset padding, computed by
   * MapScreen.
   */
  bottomOffsetPx: number;
}

// Rendered as a child of <Map>, so it can drive the camera through the
// SDK's own controls (flyTo, centerOnUser, resetBearing) instead of the raw
// MapLibre instance.
//
// Recenter is no longer a plain toolbar button here — CompassRecenterStack
// (the SDK's own pre-built compass + recenter-on-user stack) covers that,
// bottom-right, matching up-miniapps-explore/toilets' own usage: <Map
// showControls={false}> disables the SDK's built-in control stack (see
// MapScreen.tsx) in favor of this, specifically so this app exercises
// MapControlButton/CompassRecenterStack directly rather than only ever
// using <Map>'s simpler built-in showUserLocationButton path.
export function MapToolbar({ topOffset, bottomOffsetPx }: MapToolbarProps) {
  const { bearing, centerOnUser, flyTo, pitch, resetBearing } =
    useMapControls();
  const selectedPoiId = useAtomValue(selectedPoiIdAtom);
  const setGeofenceDemoOpen = useSetAtom(geofenceDemoOpenAtom);

  useEffect(() => {
    const poi = DEMO_POIS.find((candidate) => candidate.id === selectedPoiId);
    if (poi) flyTo([poi.longitude, poi.latitude], { zoom: 16 });
  }, [flyTo, selectedPoiId]);

  return (
    <>
      <div
        className="absolute left-4 z-10 flex gap-2"
        style={{ top: topOffset }}
      >
        <Button
          onClick={() => flyTo(ANNECY_CENTER, { zoom: 14 })}
          size="sm"
          variant="secondary"
        >
          Vue Annecy
        </Button>
        <Button
          onClick={() => setGeofenceDemoOpen(true)}
          size="sm"
          variant="secondary"
        >
          Zone non couverte
        </Button>
      </div>
      <CompassRecenterStack
        bearing={bearing}
        bottomOffsetPx={bottomOffsetPx}
        onCenterOnUser={() => centerOnUser()}
        onResetBearing={() => resetBearing()}
        pitch={pitch}
      />
    </>
  );
}
