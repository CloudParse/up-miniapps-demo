import { EmptyState } from "@app/components/layout/EmptyState";
import { ScreenTitle } from "@app/components/layout/ScreenTitle";
import { Badge } from "@app/components/ui/badge";
import { Button } from "@app/components/ui/button";
import { Card } from "@app/components/ui/card";
import { apiClient, getWsUrl } from "@app/services/backend";
import {
  type BroadcastWsServiceClient,
  createWsService,
  type WsConnectionStatus,
  type WsMessage,
} from "@cloudparse/up-miniapps-sdk";
import { useEffect, useState } from "react";

const STATUS_TONE: Record<
  WsConnectionStatus,
  "success" | "warning" | "neutral"
> = {
  closed: "neutral",
  connecting: "warning",
  open: "success",
};

export function RealtimeDemo() {
  const wsUrl = getWsUrl();
  const [status, setStatus] = useState<WsConnectionStatus>("closed");
  const [messages, setMessages] = useState<{ id: number; text: string }[]>([]);
  const [client, setClient] = useState<BroadcastWsServiceClient | null>(null);

  useEffect(() => {
    if (!wsUrl) return;
    const ws = createWsService({ api: apiClient });
    setClient(ws);
    const offStatus = ws.onStatusChange(setStatus);
    const offMessages = ws.onMessage((message: WsMessage) => {
      setMessages((previous) =>
        [
          { id: (previous[0]?.id ?? 0) + 1, text: JSON.stringify(message) },
          ...previous,
        ].slice(0, 8),
      );
    });
    return () => {
      offStatus();
      offMessages();
      ws.disconnect();
    };
  }, [wsUrl]);

  if (!wsUrl) {
    return (
      <div className="flex flex-col gap-4">
        <ScreenTitle title="Temps réel" />
        <EmptyState
          description="Aucune URL WebSocket reçue : le shell ne fournit pas wsUrl et VITE_BACKEND_URL n'est pas renseigné."
          title="Temps réel non configuré"
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <ScreenTitle
        subtitle="Canal diffusé, reconnexion automatique."
        title="Temps réel"
      />
      <Card className="flex items-center justify-between gap-3">
        <p className="text-sm-plus text-ink-bright">Connexion</p>
        <Badge tone={STATUS_TONE[status]}>{status}</Badge>
      </Card>
      <div className="flex gap-2">
        <Button
          className="flex-1"
          disabled={!client || status !== "closed"}
          onClick={() => void client?.connect()}
        >
          Connecter
        </Button>
        <Button
          className="flex-1"
          disabled={!client || status === "closed"}
          onClick={() => client?.disconnect()}
          variant="outline"
        >
          Déconnecter
        </Button>
      </div>
      <div className="flex flex-col gap-2">
        {messages.length === 0 ? (
          <p className="text-xs-plus text-ink-faint">
            Aucun message reçu pour l'instant.
          </p>
        ) : null}
        {messages.map((message) => (
          <Card
            className="p-3 text-xxs-minus break-all text-ink-soft"
            key={message.id}
          >
            {message.text}
          </Card>
        ))}
      </div>
    </div>
  );
}
