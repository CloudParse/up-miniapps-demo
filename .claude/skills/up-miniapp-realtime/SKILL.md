---
name: up-miniapp-realtime
description: Realtime in an Up mini-app. The API pushes over a WebSocket, the mini-app listens with createWsService (broadcast or channel mode). Use when adding a live feature, a counter that updates on its own, notifications, or when the WebSocket does not connect.
---

# Up realtime

Status: draft. Source of truth: `docs/realtime.md`. Last audited 2026-11-25.

## Shape

- The API route is `GET /api/v1/ws` (`api/app/api/routes/realtime.py`). The hub is `api/app/services/realtime_service.py`.
- The client is `createWsService({ api: apiClient })` in broadcast mode (`miniapp/src/features/tools/RealtimeDemo.tsx`). With `channelField` it is channel mode (rooms).
- The SDK client only listens. A person acts with HTTP (`createApiService`), the API then calls `hub.broadcast(...)`.
- Ping/pong: `miniapp/src/lib/pingClient.ts` sends `{"type":"ping","id":n}` on its own socket, the API answers `{"type":"pong","id":n,"serverTime":...}` to that socket only (`api/app/api/routes/realtime.py`). The screen **Temps réel** has a **Ping** button that shows the round trip. Use it first to check that realtime works.

## Steps to add a live feature

1. Add the HTTP route that changes the data (service first, route second, see `up-miniapp-api`).
2. In the route (`async def`, blocking service through `run_in_threadpool`), after the change succeeded, push a small message: `await hub.publish({"event": "thing_changed", "id": "..."})`. Get the hub with `RealtimeHubDep`. Use `publish`, not `broadcast`: it also reaches the other replicas through the cache.
3. In the mini-app, `ws.onMessage` receives it and updates the screen or reloads the data with an HTTP call. Also reload when the socket (re)opens (`onStatusChange`): a push sent while offline is lost. Create the service with `requireAuth: false` if the screen must also work in a browser tab.
4. In the Studio plugin, use `useRealtime` (`plugin/src/hooks/useRealtime.ts`): same events, and a visible chip with the state.
5. Unsubscribe and `ws.disconnect()` when the component unmounts.
6. Add a test in `api/tests/test_realtime.py` style: connect a socket with `client.websocket_connect`, call the route, assert what the socket receives.

## The demo events

`visit_recorded` (`databaseVisits`, `cacheVisits`, `at`) after `POST /demo/visit`, `counter_reset` (`cacheVisits: 0`, `at`) after `POST /admin/demo/reset-cache`. The mini-app card and the plugin page both listen, so a visit moves the plugin and a reset moves the mini-app. Table of the contract: `docs/realtime.md`, "Events of the demo".

## Rules

- Never write the socket address in the code. The platform registers `wss://api.<mini-app>.app.<domain>/api/v1/ws` and gives it to the app.
- The socket is a public broadcast channel (no cookie or token; the `Origin` is checked, `null` is the web launcher). Push no secret and no personal data. Client frames over 1024 bytes close it, 5 minutes of silence close it, 10 sockets per address. Push a ping, then let the mini-app fetch with its token.
- Limit the size and the rate of what you push.
- One process holds the sockets in memory. `hub.publish` fans out to the other replicas through the cache channel `<CACHE_KEY_PREFIX>realtime` (`services/realtime_bus.py`).
- A private channel needs a ticket checked when the socket opens. `POST /api/v1/ws-ticket` (signed in) issues a 30-second single-use ticket, the socket accepts it as `?ticket=` (`docs/realtime.md`, "Tickets"). Make it mandatory for a private channel. Do not trust a room id sent by the client alone.

## When it is connected but nothing moves

1. Open the page of the plugin: the chip shows the state and the log shows each event. No event line: the API did not push (the route failed, or it calls nothing: check `hub.publish`).
2. Events arrive but the figures stay: the page ignores the `event` name or the field (`realtimeEvents.ts`, `demoEvents.ts`).
3. Several replicas and only some screens move: the cache cannot publish (look for "realtime bus: publish failed" in the API log).

## When it does not connect

1. The screen says "Temps réel non configuré": no WebSocket address yet. Deploy the backend, or in development run both servers.
2. Status stays `connecting`: the API is not running, or the address is wrong. Check `https://api.<mini-app>.app.<domain>/api/v1/health` first.
3. A "closed before the connection is established" error once at start is a socket closed on purpose while it was opening: it is harmless if the next connection opens.
