import { greetingAtom } from "@app/atoms/greeting";
import { Button } from "@app/components/ui/button";
import { Card } from "@app/components/ui/card";
import { SkeletonBlock } from "@app/components/ui/skeleton";
import { loadGreeting } from "@app/features/home/greetingLoader";
import { useAtomValue } from "jotai";
import { useEffect } from "react";

// The demo's own backend: GET /api/v1/hello, a public route of backend/.
export function BackendGreetingCard() {
  const greeting = useAtomValue(greetingAtom);

  useEffect(() => {
    void loadGreeting();
  }, []);

  return (
    <Card className="flex flex-col gap-2">
      <p className="text-xs-plus font-medium uppercase text-ink-faint">
        Message du backend
      </p>
      {greeting.status === "ready" ? (
        <p className="font-display text-md-plus font-semibold text-ink-bright">
          {greeting.data.message}
        </p>
      ) : greeting.status === "error" ? (
        <div className="flex flex-col gap-2">
          <p className="text-xs-plus text-accent-danger">{greeting.message}</p>
          <div>
            <Button
              onClick={() => void loadGreeting(true)}
              size="sm"
              variant="secondary"
            >
              Réessayer
            </Button>
          </div>
        </div>
      ) : (
        <SkeletonBlock className="h-6 w-40" />
      )}
    </Card>
  );
}
