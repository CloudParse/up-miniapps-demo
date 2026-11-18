import { EmptyState } from "@app/components/layout/EmptyState";
import { ScreenTitle } from "@app/components/layout/ScreenTitle";
import { Button } from "@app/components/ui/button";
import { Card } from "@app/components/ui/card";
import { getErrorMessage } from "@app/lib/errors";
import { getBackendUrl, joinBackendPath } from "@app/services/backend";
import { HELLO_PATH } from "@app/services/helloService";
import { sdk } from "@cloudparse/up-miniapps-sdk";
import { useRef, useState } from "react";

const MAX_RESULTS = 6;

interface PingResult {
  id: number;
  label: string;
  detail: string;
}

export function NetworkDemo() {
  const backendUrl = getBackendUrl();
  const [results, setResults] = useState<PingResult[]>([]);
  const [pending, setPending] = useState(false);
  const lastId = useRef(0);

  const addResult = (label: string, detail: string) => {
    lastId.current += 1;
    const id = lastId.current;
    setResults((previous) =>
      [{ detail, id, label }, ...previous].slice(0, MAX_RESULTS),
    );
  };

  const ping = async (timeoutMs: number, label: string) => {
    setPending(true);
    const startedAt = performance.now();
    try {
      const response = await sdk.network.request({
        method: "GET",
        timeoutMs,
        url: joinBackendPath(HELLO_PATH),
      });
      const elapsed = Math.round(performance.now() - startedAt);
      addResult(label, `HTTP ${response.status} en ${elapsed} ms`);
    } catch (error) {
      addResult(label, getErrorMessage(error));
    } finally {
      setPending(false);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <ScreenTitle
        subtitle="Toutes les requêtes passent par le shell (sdk.network)."
        title="Réseau"
      />

      {backendUrl ? null : (
        <EmptyState
          description="Sans backend, les requêtes ne peuvent pas partir. Configure VITE_BACKEND_URL."
          title="Backend non configuré"
        />
      )}

      <Card className="flex flex-col gap-3">
        <p className="text-xs-plus text-ink-soft">
          Cible : {backendUrl ? joinBackendPath(HELLO_PATH) : "—"}
        </p>
        <Button
          disabled={!backendUrl || pending}
          onClick={() => void ping(5000, "Délai 5 s")}
        >
          Tester avec délai de 5 s
        </Button>
        <Button
          disabled={!backendUrl || pending}
          onClick={() => void ping(1, "Délai 1 ms")}
          variant="outline"
        >
          Démontrer un délai dépassé
        </Button>
      </Card>

      <div className="flex flex-col gap-2">
        {results.map((result) => (
          <Card className="flex flex-col gap-1 p-3" key={result.id}>
            <p className="text-sm-plus font-medium text-ink-bright">
              {result.label}
            </p>
            <p className="text-xs-plus text-ink-soft">{result.detail}</p>
          </Card>
        ))}
      </div>
    </div>
  );
}
