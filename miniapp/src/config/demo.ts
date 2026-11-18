import type { TabId } from "@app/config/tabs";

export interface FeatureHighlight {
  id: string;
  title: string;
  description: string;
  tab: TabId;
}

export const FEATURE_HIGHLIGHTS: readonly FeatureHighlight[] = [
  {
    description: "Carte, POI, itinéraire natif et suivi d'arrivée.",
    id: "map",
    tab: "map",
    title: "Carte et itinéraire",
  },
  {
    description: "QR code stylisé, lecture par caméra et image.",
    id: "media",
    tab: "media",
    title: "QR codes et médias",
  },
  {
    description: "Réseau, temps réel, haptique, permissions, stockage.",
    id: "tools",
    tab: "tools",
    title: "Outils système",
  },
  {
    description: "Profil, fidélité, succès, paiement de démonstration.",
    id: "account",
    tab: "account",
    title: "Compte et succès",
  },
];

export interface DemoPoi {
  id: string;
  name: string;
  description: string;
  longitude: number;
  latitude: number;
  type: "landmark" | "park" | "shop";
  emoji: string;
}

// Demo points only, around Annecy. Not real venue data.
export const DEMO_POIS: readonly DemoPoi[] = [
  {
    description: "Canaux, bateaux et vue sur les montagnes.",
    emoji: "🏞️",
    id: "old-town",
    latitude: 45.8996,
    longitude: 6.1262,
    name: "Vieille ville",
    type: "landmark",
  },
  {
    description: "Monument sur l'îlot au centre des canaux.",
    emoji: "🏰",
    id: "palais-isle",
    latitude: 45.8998,
    longitude: 6.1283,
    name: "Palais de l'Île",
    type: "landmark",
  },
  {
    description: "Jardin en bord de lac, idéal pour une pause.",
    emoji: "🌳",
    id: "jardin",
    latitude: 45.9013,
    longitude: 6.1199,
    name: "Jardin de l'Europe",
    type: "park",
  },
  {
    description: "Boutique de démonstration pour tester les POI cliquables.",
    emoji: "🛍️",
    id: "shop",
    latitude: 45.8985,
    longitude: 6.1235,
    name: "Boutique démo",
    type: "shop",
  },
];

export const ANNECY_CENTER: [number, number] = [6.1262, 45.8996];
