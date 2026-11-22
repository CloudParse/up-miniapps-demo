import { Button } from "@app/components/ui/button";
import { Card } from "@app/components/ui/card";
import { getErrorMessage } from "@app/lib/errors";
import { type DemoVisit, recordDemoVisit } from "@app/services/demoService";
import { useState } from "react";

function describe(value: number | string | null): string {
  return value === null ? "non configuré" : String(value);
}

// The demo's own resources: POST /api/v1/demo/visit writes a row in PostgreSQL, a counter in
// the cache and an object in the bucket, then reads them back. Delete it with backend/app/services/demo_service.py.
export function DemoDataCard() {
  const [visit, setVisit] = useState<DemoVisit | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function record() {
    setBusy(true);
    setError(null);
    try {
      setVisit(await recordDemoVisit());
    } catch (caught) {
      setError(getErrorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="flex flex-col gap-2">
      <p className="text-xs-plus font-medium uppercase text-ink-faint">
        Données de la mini-app
      </p>
      {visit ? (
        <ul className="flex flex-col gap-1 text-xs-plus text-ink-bright">
          <li>Base de données : {describe(visit.databaseVisits)} visite(s)</li>
          <li>Cache : {describe(visit.cacheVisits)} visite(s)</li>
          <li>
            Bucket :{" "}
            {visit.storageObject === null
              ? "non configuré"
              : "objet écrit et relu"}
          </li>
        </ul>
      ) : null}
      {error ? (
        <p className="text-xs-plus text-accent-danger">{error}</p>
      ) : null}
      <div>
        <Button
          disabled={busy}
          onClick={() => void record()}
          size="sm"
          variant="secondary"
        >
          Enregistrer une visite
        </Button>
      </div>
    </Card>
  );
}
