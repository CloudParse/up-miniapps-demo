import { atom } from "jotai";

export interface JourneyDestination {
  name: string;
  coords: [number, number];
}

export const selectedPoiIdAtom = atom<string | null>(null);

export const journeyDestinationAtom = atom<JourneyDestination | null>(null);

// Demo-only trigger for the SDK's GeofenceModal (normally shown when a
// user's real location is detected far outside the app's covered area —
// nothing to detect for real in the simulator, so MapToolbar's "Simuler
// zone non couverte" button opens it on demand instead).
export const geofenceDemoOpenAtom = atom(false);
