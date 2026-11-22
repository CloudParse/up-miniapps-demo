import {
  Banner,
  Button,
  isApiError,
  LoadingState,
  SectionHeader,
  StatTile,
} from "@cloudparse/up-backoffice-sdk";
import type { DemoOverview } from "@plugin/features/demo/types";
import { demoService } from "@plugin/services/demo";
import { Database, FolderArchive, MemoryStick, RotateCcw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

function describe(error: unknown): string {
  // isApiError, never instanceof: the error class comes from the host's copy of the SDK.
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
  const [busy, setBusy] = useState(false);

  const run = useCallback(async (call: () => Promise<DemoOverview>) => {
    setBusy(true);
    setError(null);
    try {
      setOverview(await call());
    } catch (caught) {
      setError(describe(caught));
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    run(demoService.overview);
  }, [run]);

  return (
    <div className="space-y-8">
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
            disabled={busy}
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

      {overview === null ? (
        <LoadingState />
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
