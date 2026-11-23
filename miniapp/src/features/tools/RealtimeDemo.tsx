import { EmptyState } from "@app/components/layout/EmptyState";
import { ScreenTitle } from "@app/components/layout/ScreenTitle";
import { Badge } from "@app/components/ui/badge";
import { Button } from "@app/components/ui/button";
import { Card } from "@app/components/ui/card";
import { useAction } from "@app/hooks/useAction";
import {
  createPingClient,
  type PingClient,
  type PingResult,
  type PingStatus,
} from "@app/lib/pingClient";
import { apiClient, getWsUrl } from "@app/services/backend";
import { broadcastDemoMessage } from "@app/services/demoService";
import {
  type BroadcastWsServiceClient,
  createWsService,
  type WsConnectionStatus,
  type WsMessage,
} from "@cloudparse/up-miniapps-sdk";
import { useEffect, useState } from "react";

const STATUS_LABEL: Record<PingStatus, string> = {
  closed: "déconnecté",
  connecting: "connexion…",
  open: "connecté",
};

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
  // Ping/pong: the SDK broadcast client only listens, so the ping has its own small socket
  // to the same address (src/lib/pingClient.ts). The API answers the sender only.
  const [pingStatus, setPingStatus] = useState<PingStatus>("closed");
  const [lastPong, setLastPong] = useState<PingResult | null>(null);
  const [pingLog, setPingLog] = useState<{ id: number; text: string }[]>([]);
  const [pinger, setPinger] = useState<PingClient | null>(null);
  const send = useAction(() =>
    broadcastDemoMessage(
      `Bonjour de ${new Date().toLocaleTimeString("fr-FR")}`,
    ),
  );

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

  useEffect(() => {
    if (!wsUrl) return;
    let line = 0;
    const next = createPingClient({
      onLog: (text) =>
        setPingLog((previous) =>
          [
            {
              id: ++line,
              text: `${new Date().toLocaleTimeString("fr-FR")} ${text}`,
            },
            ...previous,
          ].slice(0, 6),
        ),
      onPong: setLastPong,
      onStatus: setPingStatus,
      url: wsUrl,
    });
    setPinger(next);
    next.connect();
    return () => {
      next.disconnect();
      setPinger(null);
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
        subtitle="Canal diffusé : l'API pousse, l'app écoute. Reconnexion automatique."
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
      <Card className="flex flex-col gap-3">
        <div className="flex items-center justify-between gap-3">
          <p className="text-sm-plus text-ink-bright">Ping / pong</p>
          <Badge
            tone={
              pingStatus === "open"
                ? "success"
                : pingStatus === "connecting"
                  ? "warning"
                  : "neutral"
            }
          >
            {STATUS_LABEL[pingStatus]}
          </Badge>
        </div>
        <Button
          disabled={!pinger || pingStatus !== "open"}
          onClick={() => pinger?.ping()}
        >
          Ping
        </Button>
        {lastPong ? (
          <p className="text-sm-plus text-ink-bright">
            Pong #{lastPong.id} reçu en {lastPong.roundTripMs} ms (heure du
            serveur {new Date(lastPong.serverTime).toLocaleTimeString("fr-FR")})
          </p>
        ) : (
          <p className="text-xs-plus text-ink-faint">
            Appuie sur Ping : l'API répond par un pong, à toi seul.
          </p>
        )}
        {pingLog.map((entry) => (
          <p className="text-xxs-minus text-ink-soft break-all" key={entry.id}>
            {entry.text}
          </p>
        ))}
      </Card>
      <Button
        disabled={status !== "open" || send.state.status === "pending"}
        onClick={() => void send.run()}
        variant="secondary"
      >
        Envoyer un message à tous
      </Button>
      {send.state.status === "error" ? (
        <p className="text-sm-plus text-accent-danger">{send.state.message}</p>
      ) : null}
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
