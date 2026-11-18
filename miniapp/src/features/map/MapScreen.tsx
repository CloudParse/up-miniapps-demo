import mapStyleDark from "@app/assets/mapStyleDark.json";
import mapStyleLight from "@app/assets/mapStyleLight.json";
import { contextAtom, isDarkAtom } from "@app/atoms/context";
import { geofenceDemoOpenAtom, selectedPoiIdAtom } from "@app/atoms/map";
import { overlayAtom } from "@app/atoms/navigation";
import { ExitButton } from "@app/components/layout/ExitButton";
import { OverlayInteractive } from "@app/components/layout/OverlayInteractive";
import { TopBar } from "@app/components/layout/TopBar";
import { ANNECY_CENTER, DEMO_POIS } from "@app/config/demo";
import { APP_CONFIG } from "@app/config/env";
import { JourneyPanel } from "@app/features/map/JourneyPanel";
import { LocationPanel } from "@app/features/map/LocationPanel";
import { MapToolbar } from "@app/features/map/MapToolbar";
import { PoiOffMapIndicators } from "@app/features/map/PoiOffMapIndicators";
import { PoiSheet } from "@app/features/map/PoiSheet";
import { topBarPaddingTop } from "@app/lib/layout";
import {
  GeofenceModal,
  MapMenu,
  MapMenuItem,
  MapMenuTitle,
  SDKMapProvider,
  Map as SdkMap,
} from "@cloudparse/up-miniapps-sdk";
import type { StyleSpecification } from "@vis.gl/react-maplibre";
import { useAtom, useAtomValue, useSetAtom } from "jotai";
import { MapPin } from "lucide-react";

// MapScreen's own floating TopBar is an ExitButton (~40px) in a row with
// `pb-3` (12px) below `topBarPaddingTop` — measured 104px total at the
// 24px/48px-floor default, i.e. 56px of content+padding on top of the
// floor. Sub-elements (MapToolbar, the JourneyPanel/LocationPanel stack)
// must clear that, plus their own breathing room.
const FLOATING_HEADER_CONTENT_PX = 56;
const HEADER_GAP_PX = 8;
// MapToolbar's button row — measured 36px tall (Button size="sm").
const TOOLBAR_ROW_HEIGHT_PX = 36;
// BottomNav's own content: 8px (pt-2) + a 44px min-h-11 tap target + 8px
// (its own BOTTOM_PADDING_BASE_PX, below insetBottom) — BottomNav is always
// rendered (App.tsx never hides it for this tab), so CompassRecenterStack
// and PoiOffMapIndicators must clear its real height, not just its inset.
const BOTTOM_NAV_CONTENT_PX = 60;
const BOTTOM_STACK_GAP_PX = 12;

export function MapScreen() {
  const setSelectedPoiId = useSetAtom(selectedPoiIdAtom);
  const [overlay, setOverlay] = useAtom(overlayAtom);
  const [geofenceDemoOpen, setGeofenceDemoOpen] = useAtom(geofenceDemoOpenAtom);
  const context = useAtomValue(contextAtom);
  const isDark = useAtomValue(isDarkAtom);

  const headerClearance =
    topBarPaddingTop(context.insets.top) + FLOATING_HEADER_CONTENT_PX;
  const bottomClearance =
    BOTTOM_NAV_CONTENT_PX + (context.insets.bottom || 0) + BOTTOM_STACK_GAP_PX;

  const pois = DEMO_POIS.map((poi) => ({
    description: poi.description,
    displayMode: "marker" as const,
    emoji: poi.emoji,
    id: poi.id,
    latitude: poi.latitude,
    longitude: poi.longitude,
    name: poi.name,
    type: poi.type,
  }));

  return (
    <div className="relative h-full w-full">
      {/* Floats over the fullscreen map instead of pushing it down — see
          App.tsx, which skips its own push-down TopBar for this tab. */}
      <TopBar
        floating
        insetTop={context.insets.top}
        leading={
          <ExitButton
            mode="exit"
            onPress={() => setOverlay({ kind: "exit" })}
          />
        }
        title="Carte"
      />

      <SDKMapProvider>
        <SdkMap
          className="h-full w-full"
          drawerState="peek"
          initialViewState={{
            latitude: ANNECY_CENTER[1],
            longitude: ANNECY_CENTER[0],
            zoom: 14,
          }}
          mapStyle={
            (isDark ? mapStyleDark : mapStyleLight) as StyleSpecification
          }
          menuContent={
            <MapMenu>
              <MapMenuTitle>Lieux de démonstration</MapMenuTitle>
              {DEMO_POIS.map((poi) => (
                <MapMenuItem
                  icon={<MapPin size={18} />}
                  id={poi.id}
                  key={poi.id}
                  label={poi.name}
                  onPress={() => {
                    setSelectedPoiId(poi.id);
                    setOverlay({ kind: "poi", poiId: poi.id });
                  }}
                />
              ))}
            </MapMenu>
          }
          onPoiClick={(poi) => {
            setSelectedPoiId(String(poi.id));
            setOverlay({ kind: "poi", poiId: String(poi.id) });
          }}
          pois={pois}
          showControls={false}
          showUserLocation
        >
          {/* showControls={false} above disables <Map>'s own built-in
              control stack — MapToolbar renders CompassRecenterStack
              itself instead (see that file's own comment for why), so this
              app exercises that component directly rather than only ever
              using the simpler built-in path. */}
          <MapToolbar
            bottomOffsetPx={bottomClearance}
            topOffset={headerClearance + HEADER_GAP_PX}
          />
          <PoiOffMapIndicators
            bottomPx={bottomClearance}
            topPx={
              headerClearance +
              HEADER_GAP_PX +
              TOOLBAR_ROW_HEIGHT_PX +
              HEADER_GAP_PX
            }
          />
        </SdkMap>
      </SDKMapProvider>

      {/* The map is the whole screen (by-night's pattern); everything else
          floats on top instead of pushing it into a fraction of the height.
          `absolute` (not `fixed`) relative to this already-correctly-placed
          container, which now spans the full phone screen — the map and
          every overlay in it (the floating header above, this stack) must
          clear the SAME floating header, hence the shared
          `headerClearance` rather than a hardcoded `top-*` class.
          `pointer-events-none` on the stack, `pointer-events-auto` per card
          (OverlayInteractive) so the map stays draggable in the gaps. */}
      <div
        className="pointer-events-none absolute inset-x-0 z-20 mx-auto flex max-w-md flex-col gap-3 px-4"
        style={{
          top:
            headerClearance +
            HEADER_GAP_PX +
            TOOLBAR_ROW_HEIGHT_PX +
            HEADER_GAP_PX,
        }}
      >
        <OverlayInteractive>
          <JourneyPanel />
        </OverlayInteractive>
        <OverlayInteractive>
          <LocationPanel />
        </OverlayInteractive>
      </div>

      <PoiSheet
        onOpenChange={(open) => {
          if (!open) setOverlay({ kind: "none" });
        }}
        open={overlay.kind === "poi"}
      />

      <GeofenceModal
        appName={APP_CONFIG.appName}
        areaLabel="la ville d'Annecy et ses environs"
        isOpen={geofenceDemoOpen}
        onContinue={() => setGeofenceDemoOpen(false)}
        onExit={() => {
          setGeofenceDemoOpen(false);
          setOverlay({ kind: "exit" });
        }}
      />
    </div>
  );
}
