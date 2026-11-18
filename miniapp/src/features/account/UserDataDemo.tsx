import { Button } from "@app/components/ui/button";
import { Card } from "@app/components/ui/card";
import { Input } from "@app/components/ui/input";
import { useAction } from "@app/hooks/useAction";
import { sdk } from "@cloudparse/up-miniapps-sdk";
import { useState } from "react";

// Backend-side user data (sdk.database), not the device. The value is
// rendered as JSON so the round-trip is visible.
export function UserDataDemo() {
  const [note, setNote] = useState("");
  const read = useAction(() => sdk.database.getUserData<unknown>());
  const write = useAction((value: string) =>
    sdk.database.setUserData({ demoNote: value }),
  );

  return (
    <Card className="flex flex-col gap-3">
      <p className="text-sm-plus font-semibold text-ink-bright">
        Données utilisateur (backend)
      </p>
      <div className="flex gap-2">
        <Input
          aria-label="Note de démonstration"
          onChange={(event) => setNote(event.target.value)}
          placeholder="Note de démonstration"
          value={note}
        />
        <Button
          disabled={note.trim().length === 0}
          onClick={() => void write.run(note.trim())}
          variant="secondary"
        >
          Enregistrer
        </Button>
      </div>
      <Button onClick={() => void read.run()} size="sm" variant="ghost">
        Relire les données
      </Button>
      {read.state.status === "success" ? (
        <pre className="max-h-40 overflow-auto rounded-2xl bg-brand-card-strong p-3 text-xxs-minus text-ink-soft">
          {JSON.stringify(read.state.result, null, 2)}
        </pre>
      ) : null}
      {write.state.status === "error" || read.state.status === "error" ? (
        <p className="text-xs-plus text-accent-danger">
          {write.state.status === "error" ? write.state.message : null}
          {read.state.status === "error" ? read.state.message : null}
        </p>
      ) : null}
    </Card>
  );
}
