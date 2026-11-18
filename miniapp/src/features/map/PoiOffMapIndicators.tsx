import { selectedPoiIdAtom } from "@app/atoms/map";
import { overlayAtom } from "@app/atoms/navigation";
import { ANNECY_CENTER, DEMO_POIS, type DemoPoi } from "@app/config/demo";
import {
  EdgeDirectionIndicators,
  type EdgeDirectionItem,
} from "@cloudparse/up-miniapps-sdk";
import { useMap } from "@vis.gl/react-maplibre";
import { useSetAtom } from "jotai";
import { MapPin } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

export interface PoiOffMapIndicatorsProps {
  /** Same chrome geometry MapToolbar/CompassRecenterStack already clear —
   * see MapScreen.tsx, which computes all three from one shared layout. */
  topPx: number;
  bottomPx: number;
}

// CompassRecenterStack's own geometry (bottom-right, pr-4 = 16px inset,
// MapControlButton's own h-12/w-12 = 48px) — a chip whose bearing points
// into that corner must route around it, same as toilets/explore's own
// ToiletOffMapIndicators/OffMapEntityIndicators already do for their own
// bottom-right control stacks. Without this, EdgeDirectionIndicators has no
// way to know that corner is occupied — confirmed live by a strict review:
// nothing stopped a chip from landing directly on top of the recenter
// button, which would also block taps on it (chips render above the
// control stack, z-30 vs. z-20).
const CONTROL_COLUMN = { rightInsetPx: 16, widthPx: 48 };

const byId = new Map<string, DemoPoi>(DEMO_POIS.map((poi) => [poi.id, poi]));

function formatDistance(distanceMeters: number): string {
  if (distanceMeters < 1000) return `${Math.round(distanceMeters)} m`;
  return `${(distanceMeters / 1000).toFixed(1)} km`;
}

/**
 * Compass-style edge chips pointing toward the demo POIs currently off
 * screen — a thin app-specific wrapper around the SDK's generic
 * `EdgeDirectionIndicators` (added 2026-10-06 — this app had zero coverage
 * of it before; see AGENTS.md's "coverage audit" entry), same pattern as
 * up-miniapps-toilets' `ToiletOffMapIndicators.tsx`/up-miniapps-explore's
 * `OffMapEntityIndicators.tsx`. This app has no real distance data (no live
 * user-location tracking against the fixed demo POIs), so `distanceMeters`
 * is a straight-line haversine from the map's own CURRENT center — good
 * enough to drive the chip ordering/labels for a demo, not a claim of real
 * live distance. Recomputed on every pan/zoom (mirrors
 * `EdgeDirectionIndicators`' own internal tick/rAF pattern for direction —
 * a strict review caught that computing it once from the map's fixed
 * initial center instead would leave the distance label stale/misleading
 * the moment the user pans away from it, even though the chip's own
 * direction arrow stays live).
 */
export function PoiOffMapIndicators({
  topPx,
  bottomPx,
}: PoiOffMapIndicatorsProps) {
  const setSelectedPoiId = useSetAtom(selectedPoiIdAtom);
  const setOverlay = useSetAtom(overlayAtom);
  const { current } = useMap();
  const [tick, setTick] = useState(0);
  const rafIdRef = useRef<number | null>(null);

  useEffect(() => {
    const map = current?.getMap();
    if (!map) return;

    const schedule = () => {
      if (rafIdRef.current !== null) return;
      rafIdRef.current = requestAnimationFrame(() => {
        rafIdRef.current = null;
        setTick((t) => t + 1);
      });
    };

    map.on("move", schedule);
    return () => {
      map.off("move", schedule);
      if (rafIdRef.current !== null) cancelAnimationFrame(rafIdRef.current);
    };
  }, [current]);

  const items: EdgeDirectionItem[] = useMemo(() => {
    const map = current?.getMap();
    const center = map ? map.getCenter() : null;
    const centerLat = center?.lat ?? ANNECY_CENTER[1];
    const centerLng = center?.lng ?? ANNECY_CENTER[0];

    return DEMO_POIS.map((poi) => ({
      distanceMeters: haversineMeters(
        centerLat,
        centerLng,
        poi.latitude,
        poi.longitude,
      ),
      id: poi.id,
      lat: poi.latitude,
      lng: poi.longitude,
    }));
  }, [current, tick]);

  return (
    <EdgeDirectionIndicators
      ariaLabel={(item) => {
        const poi = byId.get(item.id);
        return `${poi?.name ?? "Lieu"} — ${formatDistance(item.distanceMeters)}`;
      }}
      budget={3}
      chrome={{
        bottomPx,
        controlColumn: CONTROL_COLUMN,
        sideMarginPx: 20,
        topPx,
      }}
      // z-30: this component has no z-index of its own (see the SDK's own
      // source) and without one rendered behind MapScreen.tsx's own
      // JourneyPanel/LocationPanel stack (z-20) — confirmed live: the
      // chip's own background-color was computing correctly, it was just
      // hidden under the "Position" mock-GPS card, visible only once that
      // card scrolled/closed. Direction chips are a navigational affordance
      // and should sit above informational overlay cards, not under them.
      className="z-30"
      formatDistance={formatDistance}
      items={items}
      onSelect={(item) => {
        setSelectedPoiId(item.id);
        setOverlay({ kind: "poi", poiId: item.id });
      }}
      renderIcon={() => (
        <MapPin className="text-ink-deep" size={14} strokeWidth={2.5} />
      )}
    />
  );
}

const EARTH_RADIUS_METERS = 6371000;

function haversineMeters(
  lat1: number,
  lng1: number,
  lat2: number,
  lng2: number,
): number {
  const toRad = (deg: number) => (deg * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLng = toRad(lng2 - lng1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2;
  return EARTH_RADIUS_METERS * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}
