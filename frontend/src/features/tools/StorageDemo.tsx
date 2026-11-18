import { ScreenTitle } from "@app/components/layout/ScreenTitle";
import { Button } from "@app/components/ui/button";
import { Card } from "@app/components/ui/card";
import { Input } from "@app/components/ui/input";
import { useAction } from "@app/hooks/useAction";
import { sdk } from "@cloudparse/up-miniapps-sdk";
import { useState } from "react";

export function StorageDemo() {
  const [key, setKey] = useState("preference");
  const [value, setValue] = useState("");
  const [lookup, setLookup] = useState<string | null>(null);
  const writeLocal = useAction((k: string, v: string) => sdk.storage.set(k, v));
  const readLocal = useAction((k: string) => sdk.storage.get(k));
  const listLocal = useAction(() => sdk.storage.getAll());
  const writeSecure = useAction((k: string, v: string) =>
    sdk.secureStore.set(k, v),
  );
  const readSecure = useAction((k: string) => sdk.secureStore.get(k));

  return (
    <div className="flex flex-col gap-4">
      <ScreenTitle
        subtitle="Données propres à cette mini-app, isolées par le shell."
        title="Stockage"
      />

      <Card className="flex flex-col gap-3">
        <Input
          aria-label="Clé"
          onChange={(event) => setKey(event.target.value)}
          placeholder="Clé"
          value={key}
        />
        <Input
          aria-label="Valeur"
          onChange={(event) => setValue(event.target.value)}
          placeholder="Valeur"
          value={value}
        />
        <div className="grid grid-cols-2 gap-2">
          <Button
            onClick={() => void writeLocal.run(key, value)}
            variant="secondary"
          >
            Enregistrer
          </Button>
          <Button
            onClick={async () => {
              const result = await readLocal.run(key);
              setLookup(result ?? "(vide)");
            }}
            variant="secondary"
          >
            Lire
          </Button>
        </div>
        <Button onClick={() => void listLocal.run()} size="sm" variant="ghost">
          Lister toutes les clés
        </Button>
        <p className="text-xs-plus text-ink-faint">
          Stocké localement sur l'appareil.
        </p>
        {lookup !== null ? (
          <p className="text-sm-plus text-ink-bright">Valeur : {lookup}</p>
        ) : null}
        {listLocal.state.status === "success" ? (
          <pre className="max-h-32 overflow-auto rounded-2xl bg-brand-card-strong p-3 text-xxs-minus text-ink-soft">
            {JSON.stringify(listLocal.state.result, null, 2)}
          </pre>
        ) : null}
        {writeLocal.state.status === "error" ? (
          <p className="text-xs-plus text-accent-danger">
            {writeLocal.state.message}
          </p>
        ) : null}
      </Card>

      <Card className="flex flex-col gap-3" tone="strong">
        <p className="text-sm-plus font-medium text-ink-bright">
          Stockage sécurisé
        </p>
        <Button
          onClick={() => void writeSecure.run(key, value)}
          variant="secondary"
        >
          Enregistrer dans le coffre
        </Button>
        <Button
          onClick={() => void readSecure.run(key)}
          size="sm"
          variant="ghost"
        >
          Lire depuis le coffre
        </Button>
        <p className="text-xs-plus text-ink-faint">
          Keychain / Keystore de l'appareil. Lecture :{" "}
          {readSecure.state.status === "success"
            ? (readSecure.state.result ?? "(vide)")
            : "—"}
        </p>
      </Card>
    </div>
  );
}
