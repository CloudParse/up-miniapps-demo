import { Home, Map as MapIcon, QrCode, UserRound, Wrench } from "lucide-react";
import type { ComponentType } from "react";

export type TabId = "home" | "map" | "tools" | "media" | "account";

export interface TabDefinition {
  id: TabId;
  label: string;
  icon: ComponentType<{ size?: number; strokeWidth?: number }>;
}

export const TABS: readonly TabDefinition[] = [
  { icon: Home, id: "home", label: "Accueil" },
  { icon: MapIcon, id: "map", label: "Carte" },
  { icon: Wrench, id: "tools", label: "Outils" },
  { icon: QrCode, id: "media", label: "Médias" },
  { icon: UserRound, id: "account", label: "Compte" },
];
