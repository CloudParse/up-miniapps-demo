import { Badge } from "@app/components/ui/badge";
import { Button } from "@app/components/ui/button";
import { Card } from "@app/components/ui/card";
import { Input } from "@app/components/ui/input";
import { useAction } from "@app/hooks/useAction";
import { sdk } from "@cloudparse/up-miniapps-sdk";
import { useState } from "react";

// Payment is not available yet: no host handles PAYMENT_REQUEST (neither the shell nor the
// website). The card says so and the points spend below still works everywhere.
export function PaymentDemo() {
  const [intentUuid, setIntentUuid] = useState("");
  const spend = useAction((uuid: string) => sdk.fidelity.spendFPoints(uuid));

  return (
    <Card className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm-plus font-semibold text-ink-bright">
          Paiement et points
        </p>
        <Badge tone="warning">Paiement : bientôt disponible</Badge>
      </div>

      <div className="flex flex-col gap-2">
        <Button disabled variant="outline">
          Paiement
        </Button>
        <p className="text-xs-plus text-ink-faint">
          Bientôt disponible. Le paiement n'est pas encore géré par l'app UP ni
          par le site.
        </p>
      </div>

      <div className="flex flex-col gap-2">
        <p className="text-xs-plus text-ink-soft">
          Autorisation de dépense de points : colle l'UUID d'intention généré
          par ton backend.
        </p>
        <div className="flex gap-2">
          <Input
            aria-label="UUID d'intention"
            onChange={(event) => setIntentUuid(event.target.value)}
            placeholder="UUID d'intention"
            value={intentUuid}
          />
          <Button
            disabled={intentUuid.trim().length === 0}
            onClick={() => void spend.run(intentUuid.trim())}
            variant="secondary"
          >
            Autoriser
          </Button>
        </div>
        {spend.state.status === "success" ? (
          <p className="text-xs-plus text-accent-success">
            {spend.state.result.success
              ? "Dépense autorisée"
              : "Dépense refusée"}
          </p>
        ) : null}
        {spend.state.status === "error" ? (
          <p className="text-xs-plus text-accent-danger">
            {spend.state.message}
          </p>
        ) : null}
      </div>
    </Card>
  );
}
