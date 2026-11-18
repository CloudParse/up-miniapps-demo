import { balanceAtom } from "@app/atoms/account";
import { isDarkAtom } from "@app/atoms/context";
import { EmptyState } from "@app/components/layout/EmptyState";
import { Button } from "@app/components/ui/button";
import { Card } from "@app/components/ui/card";
import { SkeletonBlock } from "@app/components/ui/skeleton";
import { useAction } from "@app/hooks/useAction";
import { accountService } from "@app/services/accountService";
import { type IFidelityTransaction, sdk } from "@cloudparse/up-miniapps-sdk";
import { useAtomValue } from "jotai";
import { useState } from "react";

export function FidelityCard() {
  const balance = useAtomValue(balanceAtom);
  const isDark = useAtomValue(isDarkAtom);
  const [history, setHistory] = useState<IFidelityTransaction[] | null>(null);
  const historyAction = useAction(() => accountService.getHistory(10));

  const loadHistory = async () => {
    const result = await historyAction.run();
    if (result) setHistory(result);
  };

  return (
    <Card className="flex flex-col gap-4">
      <div>
        <p className="text-xs-plus font-medium uppercase text-ink-faint">
          Points de fidélité
        </p>
        {balance.status === "ready" ? (
          <p className="mt-1 text-2xl-plus font-semibold text-ink-bright">
            {balance.data.balance.toLocaleString("fr-FR")}{" "}
            <span className="text-sm-plus font-medium text-ink-soft">
              {balance.data.currency}
            </span>
          </p>
        ) : balance.status === "error" ? (
          <p className="mt-1 text-sm-plus text-accent-danger">
            {balance.message}
          </p>
        ) : (
          <SkeletonBlock className="mt-2 h-8 w-40" />
        )}
      </div>

      <div className="flex flex-wrap gap-2">
        <Button
          onClick={() => void loadHistory()}
          size="sm"
          variant="secondary"
        >
          Charger l'historique
        </Button>
        <Button
          onClick={() => void sdk.fidelity.showHistory({ isDark })}
          size="sm"
          variant="outline"
        >
          Historique natif
        </Button>
      </div>

      {historyAction.state.status === "error" ? (
        <p className="text-sm-plus text-accent-danger">
          {historyAction.state.message}
        </p>
      ) : null}

      {history === null ? null : history.length === 0 ? (
        <EmptyState
          description="Aucune transaction pour le moment."
          title="Historique vide"
        />
      ) : (
        <ul className="flex flex-col divide-y divide-brand-border">
          {history.map((transaction) => (
            <li
              className="flex items-center justify-between gap-3 py-3"
              key={transaction.id}
            >
              <div className="min-w-0">
                <p className="truncate text-sm-plus text-ink-bright">
                  {transaction.description}
                </p>
                <p className="text-xs-plus text-ink-faint">
                  {new Date(transaction.date).toLocaleDateString("fr-FR")}
                </p>
              </div>
              <p
                className={
                  transaction.type === "credit"
                    ? "shrink-0 text-sm-plus font-semibold text-accent-success"
                    : "shrink-0 text-sm-plus font-semibold text-accent-danger"
                }
              >
                {transaction.type === "credit" ? "+" : "−"}
                {transaction.amount}
              </p>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
