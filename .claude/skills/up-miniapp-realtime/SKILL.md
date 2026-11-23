---
name: up-miniapp-realtime
description: Realtime in an Up mini-app. The API pushes over a WebSocket, the mini-app listens with createWsService (broadcast or channel mode). Use when adding a live feature, a counter that updates on its own, notifications, or when the WebSocket does not connect.
---

# Up realtime

Status: draft. Source of truth: `docs/realtime.md`. Last audited 2026-11-23.

## Shape

- The API route is `GET /api/v1/ws` (`api/app/api/routes/realtime.py`). The hub is `api/app/services/realtime_service.py`.
- The client is `createWsService({ api: apiClient })` in broadcast mode (`miniapp/src/features/tools/RealtimeDemo.tsx`). With `channelField` it is channel mode (rooms).
- The SDK client only listens. A person acts with HTTP (`createApiService`), the API then calls `hub.broadcast(...)`.
- Ping/pong: `miniapp/src/lib/pingClient.ts` sends `{"type":"ping","id":n}` on its own socket, the API answers `{"type":"pong","id":n,"serverTime":...}` to that socket only (`api/app/api/routes/realtime.py`). The screen **Temps réel** has a **Ping** button that shows the round trip. Use it first to check that realtime works.

## Steps to add a live feature

1. Add the HTTP route that changes the data (service first, route second, see `up-miniapp-api`).
2. In the service, after the change, push a small message: `await hub.broadcast({"event": "thing_changed", "id": "..."})`. Get the hub with `RealtimeHubDep`.
3. In the mini-app, `ws.onMessage` receives it and reloads the data with an HTTP call.
4. Unsubscribe and `ws.disconnect()` when the component unmounts.
5. Add a test in `api/tests/test_realtime.py` style: connect a socket with `client.websocket_connect`, call the route, assert what the socket receives.

## Rules

- Never write the socket address in the code. The platform registers `wss://api.<mini-app>.app.<domain>/api/v1/ws` and gives it to the app.
- The socket is a public broadcast channel (no cookie or token; the `Origin` is checked, `null` is the web launcher). Push no secret and no personal data. Client frames over 1024 bytes close it, 5 minutes of silence close it, 10 sockets per address. Push a ping, then let the mini-app fetch with its token.
- Limit the size and the rate of what you push.
- One process holds the sockets in memory. For several replicas, fan out through the cache (keys and channels start with `CACHE_KEY_PREFIX`).
- A private channel needs a ticket checked when the socket opens. Do not trust a room id sent by the client alone.

## When it does not connect

1. The screen says "Temps réel non configuré": no WebSocket address yet. Deploy the backend, or in development run both servers.
2. Status stays `connecting`: the API is not running, or the address is wrong. Check `https://api.<mini-app>.app.<domain>/api/v1/health` first.
3. A "closed before the connection is established" error once at start is a socket closed on purpose while it was opening: it is harmless if the next connection opens.
