import { Badge } from "@app/components/ui/badge";
import { Button } from "@app/components/ui/button";
import { Card } from "@app/components/ui/card";
import { Input } from "@app/components/ui/input";
import { useAction } from "@app/hooks/useAction";
import { sdk, useIsMocked } from "@cloudparse/up-miniapps-sdk";
import { useState } from "react";

const DEMO_PAYMENT = {
  amount: 1,
  currency: "EUR",
  items: [{ item: "Up Demo", price: 1, quantity: 1 }],
  total: 1,
};

// A real payment request charges real money on a device. The demo only runs
// inside the simulator (BridgeMocker), where no transaction can happen.
export function PaymentDemo() {
  const isMocked = useIsMocked();
  const payment = useAction(() => sdk.payment.request(DEMO_PAYMENT));
  const [intentUuid, setIntentUuid] = useState("");
  const spend = useAction((uuid: string) => sdk.fidelity.spendFPoints(uuid));

  return (
    <Card className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm-plus font-semibold text-ink-bright">
          Paiement et points
        </p>
        <Badge tone="warning">Démo</Badge>
      </div>

      <div className="flex flex-col gap-2">
        <Button
          disabled={!isMocked}
          onClick={() => void payment.run()}
          variant="outline"
        >
          Paiement de démonstration (1,00 €)
        </Button>
        {!isMocked ? (
          <p className="text-xs-plus text-ink-faint">
            Désactivé sur l'appareil : une vraie demande de paiement débiterait
            une carte.
          </p>
        ) : null}
        {payment.state.status === "success" ? (
          <p className="text-xs-plus text-accent-success">
            Simulé — transaction {payment.state.result.transactionId}
          </p>
        ) : null}
        {payment.state.status === "error" ? (
          <p className="text-xs-plus text-accent-danger">
            {payment.state.message}
          </p>
        ) : null}
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
