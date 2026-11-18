import { type ToolsPage, toolsPageAtom } from "@app/atoms/navigation";
import { ScreenTitle } from "@app/components/layout/ScreenTitle";
import { Card } from "@app/components/ui/card";
import { HapticsDemo } from "@app/features/tools/HapticsDemo";
import { NetworkDemo } from "@app/features/tools/NetworkDemo";
import { PermissionsDemo } from "@app/features/tools/PermissionsDemo";
import { RealtimeDemo } from "@app/features/tools/RealtimeDemo";
import { StorageDemo } from "@app/features/tools/StorageDemo";
import { SystemDemo } from "@app/features/tools/SystemDemo";
import { UiKitDemo } from "@app/features/tools/UiKitDemo";
import { useAtom } from "jotai";
import {
  ChevronRight,
  Database,
  LayoutGrid,
  type LucideIcon,
  Network,
  Radio,
  Settings2,
  ShieldCheck,
  Vibrate,
} from "lucide-react";

interface ToolEntry {
  id: Exclude<ToolsPage, "index">;
  title: string;
  description: string;
  icon: LucideIcon;
}

const TOOL_ENTRIES: readonly ToolEntry[] = [
  {
    description: "Requêtes via sdk.network, délais d'expiration.",
    icon: Network,
    id: "network",
    title: "Réseau",
  },
  {
    description: "WebSocket avec état de connexion et messages.",
    icon: Radio,
    id: "realtime",
    title: "Temps réel",
  },
  {
    description: "Les huit styles de retour haptique.",
    icon: Vibrate,
    id: "haptics",
    title: "Haptique",
  },
  {
    description: "Caméra, localisation et profil.",
    icon: ShieldCheck,
    id: "permissions",
    title: "Permissions",
  },
  {
    description: "Stockage local et sécurisé.",
    icon: Database,
    id: "storage",
    title: "Stockage",
  },
  {
    description: "Carrousel, tirer pour actualiser, modale, barres système.",
    icon: LayoutGrid,
    id: "ui-kit",
    title: "Interface",
  },
  {
    description: "Contexte shell, événements, journal et activité.",
    icon: Settings2,
    id: "system",
    title: "Système",
  },
];

export function ToolsScreen() {
  const [page, setPage] = useAtom(toolsPageAtom);

  if (page === "index") {
    return (
      <div className="flex-1 overflow-y-auto px-4 pt-1 pb-6">
        <ScreenTitle
          subtitle="Chaque capacité du SDK, démontrée en direct."
          title="Outils"
        />
        <div className="flex flex-col gap-3">
          {TOOL_ENTRIES.map((entry) => {
            const Icon = entry.icon;
            return (
              <button
                className="text-left"
                key={entry.id}
                onClick={() => setPage(entry.id)}
                type="button"
              >
                <Card className="flex items-center gap-4">
                  <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-brand-card-strong text-accent-primary">
                    <Icon size={22} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm-plus font-semibold text-ink-bright">
                      {entry.title}
                    </p>
                    <p className="text-xs-plus text-ink-soft">
                      {entry.description}
                    </p>
                  </div>
                  <ChevronRight className="text-ink-faint" size={20} />
                </Card>
              </button>
            );
          })}
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-y-auto px-4 pt-1 pb-6">
      {page === "network" ? <NetworkDemo /> : null}
      {page === "realtime" ? <RealtimeDemo /> : null}
      {page === "haptics" ? <HapticsDemo /> : null}
      {page === "permissions" ? <PermissionsDemo /> : null}
      {page === "storage" ? <StorageDemo /> : null}
      {page === "ui-kit" ? <UiKitDemo /> : null}
      {page === "system" ? <SystemDemo /> : null}
    </div>
  );
}
