import { contextAtom, isDarkAtom } from "@app/atoms/context";
import { appendEventAtom, eventLogAtom } from "@app/atoms/eventLog";
import { ScreenTitle } from "@app/components/layout/ScreenTitle";
import { Button } from "@app/components/ui/button";
import { Card } from "@app/components/ui/card";
import { Input } from "@app/components/ui/input";
import { useAction } from "@app/hooks/useAction";
import { getBackendUrl } from "@app/services/backend";
import { sdk } from "@cloudparse/up-miniapps-sdk";
import { useAtomValue, useSetAtom } from "jotai";
import { useState } from "react";

export function SystemDemo() {
  const context = useAtomValue(contextAtom);
  const isDark = useAtomValue(isDarkAtom);
  const events = useAtomValue(eventLogAtom);
  const appendEvent = useSetAtom(appendEventAtom);
  const [activityTitle, setActivityTitle] = useState("Up Demo");
  const saveContext = useAction(() =>
    sdk.updateContext({ demoSavedAt: new Date().toISOString() }),
  );
  const startActivity = useAction((title: string) =>
    sdk.activity.start(`demo-${Date.now()}`, title, "En cours"),
  );
  const env = sdk.getEnv();

  return (
    <div className="flex flex-col gap-4">
      <ScreenTitle
        subtitle="Contexte, événements et diagnostic."
        title="Système"
      />

      <Card className="flex flex-col gap-2 text-xs-plus text-ink-soft">
        <p>Thème : {isDark ? "sombre" : "clair"}</p>
        <p>
          Insets — haut {context.insets.top}, bas {context.insets.bottom},
          gauche {context.insets.left}, droite {context.insets.right}
        </p>
        <p>
          Variables env :{" "}
          {env ? Object.keys(env).join(", ") || "aucune" : "pas encore reçues"}
        </p>
        <p>Backend : {getBackendUrl() ?? "non configuré"}</p>
      </Card>

      <Card className="flex flex-col gap-3">
        <Button onClick={() => void saveContext.run()} variant="secondary">
          Enregistrer le contexte (updateContext)
        </Button>
        <Button
          onClick={() => {
            sdk.debug.log("demo", new Date().toISOString());
            appendEvent({ label: "debug.log envoyé", source: "app" });
          }}
          variant="outline"
        >
          Envoyer un log au shell
        </Button>
        {saveContext.state.status === "error" ? (
          <p className="text-xs-plus text-accent-danger">
            {saveContext.state.message}
          </p>
        ) : null}
      </Card>

      <Card className="flex flex-col gap-3">
        <p className="text-sm-plus font-medium text-ink-bright">
          Activité en direct
        </p>
        <Input
          aria-label="Titre de l'activité"
          onChange={(event) => setActivityTitle(event.target.value)}
          value={activityTitle}
        />
        <Button
          onClick={() => void startActivity.run(activityTitle)}
          variant="secondary"
        >
          Démarrer l'activité
        </Button>
        {startActivity.state.status === "error" ? (
          <p className="text-xs-plus text-accent-danger">
            {startActivity.state.message}
          </p>
        ) : null}
      </Card>

      <section className="flex flex-col gap-2">
        <p className="font-display text-md-plus font-semibold text-ink-bright">
          Journal des événements
        </p>
        {events.length === 0 ? (
          <p className="text-xs-plus text-ink-faint">
            Aucun événement pour l'instant.
          </p>
        ) : null}
        {events.map((entry) => (
          <Card
            className="flex items-center justify-between gap-3 p-3"
            key={entry.id}
          >
            <span className="text-xs-plus text-ink-bright">{entry.label}</span>
            <span className="text-xxs-minus text-ink-faint">
              {entry.source} · {entry.at}
            </span>
          </Card>
        ))}
      </section>
    </div>
  );
}
