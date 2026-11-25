import {
  Banner,
  Button,
  isApiError,
  LoadingState,
  SectionHeader,
  StatTile,
} from "@cloudparse/up-backoffice-sdk";
import { RealtimeStatus } from "@plugin/features/demo/RealtimeStatus";
import {
  applyDemoEvent,
  describeEvent,
  isDemoEvent,
  VISIT_RECORDED,
} from "@plugin/features/demo/realtimeEvents";
import type { DemoOverview } from "@plugin/features/demo/types";
import { useRealtime } from "@plugin/hooks/useRealtime";
import { demoService } from "@plugin/services/demo";
import { Database, FolderArchive, MemoryStick, RotateCcw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

function isNotServed(error: unknown): boolean {
  // isApiError, never instanceof: the error class comes from the host's copy of the SDK.
  return isApiError(error) && error.status === 404;
}

function describe(error: unknown): string {
  if (isApiError(error)) {
    return error.status === 403
      ? "The API refuses this account: it needs the mini-app administrator scope."
      : `The API answered ${error.status}: ${error.message}`;
  }
  return error instanceof Error ? error.message : "Unexpected error.";
}

function show(value: number | null): string {
  return value === null ? "not configured" : String(value);
}

export function DemoPage() {
  const [overview, setOverview] = useState<DemoOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notServed, setNotServed] = useState(false);
  const [busy, setBusy] = useState(false);

  const run = useCallback(async (call: () => Promise<DemoOverview>) => {
    setBusy(true);
    setError(null);
    try {
      setOverview(await call());
    } catch (caught) {
      if (isNotServed(caught)) setNotServed(true);
      else setError(describe(caught));
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    run(demoService.overview);
  }, [run]);

  // Live updates: the API pushes `visit_recorded` and `counter_reset` (docs/realtime.md).
  // The figures change at once from the event, then the overview is read again from the API:
  // it holds what the event does not carry (the bucket) and it replaces a missed push.
  const refresh = useCallback(async () => {
    try {
      setOverview(await demoService.overview());
    } catch {
      // Not served or unreachable: the page already shows why, the next push tries again.
    }
  }, []);
  const realtime = useRealtime({
    describe: describeEvent,
    onEvent: (event) => {
      if (!isDemoEvent(event)) return;
      setOverview((current) =>
        current ? applyDemoEvent(current, event) : current,
      );
      // The bucket count is not in `visit_recorded`: read it. A reset carries everything.
      if (event.event === VISIT_RECORDED) void refresh();
    },
    onOpen: () => void refresh(),
  });

  return (
    <div className="space-y-8">
      {notServed && (
        <Banner
          message="The demo routes are not served in production: the API answers 404. Replace this page and the routes /admin/demo/* with your own."
          variant="warning"
        />
      )}
      {error && (
        <Banner
          message={error}
          onClose={() => setError(null)}
          variant="error"
        />
      )}

      <SectionHeader
        actions={
          <Button
            disabled={busy || notServed}
            onClick={() => run(demoService.resetCache)}
            variant="secondary"
          >
            <RotateCcw className="size-4" />
            Reset the cache counter
          </Button>
        }
        description="Each figure is read by the mini-app API, not by the plugin."
        title="Demo resources"
      />

      <RealtimeStatus realtime={realtime} />

      {overview === null ? (
        notServed ? null : (
          <LoadingState />
        )
      ) : (
        <div className="grid gap-4 sm:grid-cols-3">
          <StatTile
            hint="PostgreSQL, table demo_visits"
            icon={Database}
            label="Visits (database)"
            value={show(overview.databaseVisits)}
          />
          <StatTile
            hint="Cache, key <prefix>demo:visits"
            icon={MemoryStick}
            label="Visits (cache)"
            value={show(overview.cacheVisits)}
          />
          <StatTile
            hint="Bucket, objects under demo/"
            icon={FolderArchive}
            label="Objects (bucket)"
            value={show(overview.storageObjects)}
          />
        </div>
      )}
    </div>
  );
}
