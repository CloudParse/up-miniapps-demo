import { Button } from "@app/components/ui/button";
import { helloStateAtom, loadHelloAtom } from "@app/features/hello/atoms";
import { GreetingCard } from "@app/features/hello/components/GreetingCard";
import { GreetingError } from "@app/features/hello/components/GreetingError";
import { GreetingSkeleton } from "@app/features/hello/components/GreetingSkeleton";
import { HELLO_ENDPOINT } from "@app/services/helloService";
import { useAtomValue, useSetAtom } from "jotai";
import { RefreshCw } from "lucide-react";
import { useEffect } from "react";

// Composition only: state lives in atoms, rendering in the components.
export function HelloScreen() {
  const state = useAtomValue(helloStateAtom);
  const loadHello = useSetAtom(loadHelloAtom);

  useEffect(() => {
    void loadHello();
  }, [loadHello]);

  return (
    <section className="flex flex-1 flex-col items-center justify-center gap-8 px-6 pb-10">
      <div className="w-full max-w-sm rounded-3xl border border-brand-border bg-brand-card/60 px-6 py-10 shadow-panel backdrop-blur-xl">
        {state.phase === "loading" ? <GreetingSkeleton /> : null}
        {state.phase === "ready" ? (
          <GreetingCard endpoint={HELLO_ENDPOINT} greeting={state.greeting} />
        ) : null}
        {state.phase === "error" ? (
          <GreetingError
            message={state.message}
            onRetry={() => void loadHello()}
          />
        ) : null}
      </div>
      {state.phase === "ready" ? (
        <Button onClick={() => void loadHello()} variant="outline">
          <RefreshCw size={16} />
          Fetch again
        </Button>
      ) : null}
    </section>
  );
}
