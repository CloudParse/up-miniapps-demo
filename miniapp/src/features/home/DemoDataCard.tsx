import { Badge } from "@app/components/ui/badge";
import { Button } from "@app/components/ui/button";
import { Card } from "@app/components/ui/card";
import { useDemoLive } from "@app/hooks/useDemoLive";
import { liveStatusLabel } from "@app/lib/demoEvents";
import { getErrorMessage } from "@app/lib/errors";
import {
  DEMO_DEV_ONLY_MESSAGE,
  type DemoVisit,
  isDemoAvailable,
  isDemoServed,
  recordDemoVisit,
} from "@app/services/demoService";
import { useEffect, useState } from "react";

// `null` is "not known yet" before the first read, "not configured" once the API answered.
function describeCount(value: number | null, loaded: boolean): string {
  if (value !== null) return String(value);
  return loaded ? "non configuré" : "—";
}

const STATUS_TONE = {
  closed: "neutral",
  connecting: "warning",
  open: "success",
} as const;

// The demo's own resources: POST /api/v1/demo/visit writes a row in PostgreSQL, a counter in
// the cache and an object in the bucket, then reads them back. Not served in production (the
// card then stays hidden). Delete it with api/app/services/demo_service.py before shipping.
export function DemoDataCard() {
  const [visit, setVisit] = useState<DemoVisit | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [served, setServed] = useState(false);
  // The counters are live: a visit recorded here or a reset made in the Studio plugin
  // reaches this card through the WebSocket (docs/realtime.md, "Events of the demo").
  const live = useDemoLive(isDemoAvailable() && served);

  useEffect(() => {
    void isDemoServed().then(setServed);
  }, []);

  async function record() {
    setBusy(true);
    setError(null);
    try {
      const next = await recordDemoVisit();
      setVisit(next);
      live.set({
        cacheVisits: next.cacheVisits,
        databaseVisits: next.databaseVisits,
      });
    } catch (caught) {
      setError(getErrorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  if (!isDemoAvailable()) {
    return (
      <Card className="text-xs-plus text-ink-soft">
        {DEMO_DEV_ONLY_MESSAGE}
      </Card>
    );
  }
  if (!served) return null;

  return (
    <Card className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs-plus font-medium uppercase text-ink-faint">
          Données de la mini-app
        </p>
        <Badge data-testid="realtime-status" tone={STATUS_TONE[live.status]}>
          Temps réel : {liveStatusLabel(live.status, live.everOpened)}
        </Badge>
      </div>
      <ul className="flex flex-col gap-1 text-xs-plus text-ink-bright">
        <li data-testid="database-visits">
          Base de données :{" "}
          {describeCount(live.counters.databaseVisits, live.loaded)} visite(s)
        </li>
        <li data-testid="cache-visits">
          Cache : {describeCount(live.counters.cacheVisits, live.loaded)}{" "}
          visite(s)
        </li>
        {visit ? (
          <li>
            Bucket :{" "}
            {visit.storageObject === null
              ? "non configuré"
              : "objet écrit et relu"}
          </li>
        ) : null}
      </ul>
      {live.lastEventAt ? (
        <p className="text-xxs-minus text-ink-faint">
          Dernière mise à jour en direct à{" "}
          {live.lastEventAt.toLocaleTimeString("fr-FR")}
        </p>
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
