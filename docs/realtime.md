# Realtime: the WebSocket of your API

The API pushes, the mini-app listens. Typical use: a person reacts, the API stores it and tells every other open mini-app. Last audited: 2026-11-25.

## The pieces

| Piece | File | Role |
| --- | --- | --- |
| Socket route | `api/app/api/routes/realtime.py`, `GET /api/v1/ws` (WebSocket) | Accepts connections, keeps them in the hub, drops them when they leave. |
| Hub | `api/app/services/realtime_service.py` (`RealtimeHub`) | Holds the open sockets (200 at most, 10 per client address) and broadcasts a message to all of them at once. A socket that fails or does not read within 2 seconds is dropped and closed. |
| Ticket route | `api/app/api/routes/realtime.py`, `POST /api/v1/ws-ticket`; `api/app/services/ticket_service.py` | Signed in (scoped Hub token). Returns `{ "ticket": "...", "expiresIn": 30 }`. See "Tickets". |
| Push example | `POST /api/v1/demo/broadcast` (development only, signed-in member) | Body `{ "text": "..." }`. Pushes `{ "event": "demo_message", "text": "..." }` to every open socket. |
| Bus | `api/app/services/realtime_bus.py` | Carries a message to the other replicas of the API through the cache (Valkey publish and subscribe). See "Several replicas". |
| Demo events | `visit_recorded`, `counter_reset` (`api/app/api/routes/demo.py`) | Pushed by `POST /demo/visit` and `POST /admin/demo/reset-cache`. See "Events of the demo". |
| Live card | `miniapp/src/features/home/DemoDataCard.tsx`, `miniapp/src/hooks/useDemoLive.ts` | The counters of the home screen. They follow the events, with a status chip "Temps réel : connecté". |
| Plugin client | `plugin/src/lib/realtimeClient.ts`, `plugin/src/hooks/useRealtime.ts`, `plugin/src/features/demo/RealtimeStatus.tsx` | The Studio page opens its own socket and shows its state. See "The plugin". |
| Client | `miniapp/src/features/tools/RealtimeDemo.tsx` | `createWsService` in broadcast mode. Shows the status and the messages received. |
| Ping client | `miniapp/src/lib/pingClient.ts` | A small socket to the same address that sends `ping` and shows the `pong` with the round trip. |

Run both servers, open the screen **Outils** then **Temps réel**, press **Envoyer un message à tous**: the message goes to the API with HTTP and comes back through the socket.

Press **Ping** to see the socket work in both directions:

1. The mini-app sends `{ "type": "ping", "id": 1 }` over the socket.
2. The API answers `{ "type": "pong", "id": 1, "serverTime": "<ISO 8601>" }` to THAT socket only. It is not a broadcast.
3. The screen shows `Pong #1 reçu en 12 ms` and a log of the last messages. The badge says `connecté` or `déconnecté`.

The round trip is measured by the mini-app with its own clock. The `id` is a small integer chosen by the client to match the pong. A socket may ping 5 times per second: more are dropped without an answer.

## Events of the demo

Every message is a JSON object with an `event` name. Counters only: it goes to every socket.

| Event | Pushed by | Fields |
| --- | --- | --- |
| `visit_recorded` | `POST /api/v1/demo/visit` (the button "Enregistrer une visite" of the mini-app), after the write succeeded | `databaseVisits` (int or null), `cacheVisits` (int or null), `at` (ISO 8601) |
| `counter_reset` | `POST /api/v1/admin/demo/reset-cache` (the button "Reset the cache counter" of the plugin), after the reset | `cacheVisits` (always 0), `at` (ISO 8601) |
| `demo_message` | `POST /api/v1/demo/broadcast` | `text` |

Both screens update at once:
- the mini-app card "Données de la mini-app" and the plugin page "Resources" both listen;
- a visit made in the mini-app moves the figures of the plugin, and a reset made in the plugin moves the figures of the mini-app;
- a route that fails (4xx, 5xx) pushes nothing.

Both screens also read the counters again from the API each time their socket opens (`GET /api/v1/demo/counters` for the mini-app, `GET /api/v1/admin/demo/overview` for the plugin). A push sent while a screen was offline is therefore never lost.

To add your own event: build the dict in `realtime_service.py` (like `visit_recorded`), call `await hub.publish(event)` after the change (not `broadcast`: `publish` also reaches the other replicas), and handle the `event` name on both sides. Routes that push are `async def`, and call the blocking service with `run_in_threadpool`.

## The plugin

The Studio plugin is a second client of the same socket. The SDK of the Studio has no WebSocket helper, so the plugin owns a small client (`plugin/src/lib/realtimeClient.ts`):

1. The address is `application.wsBackendUrl` from `usePluginHost()`. The Studio registers it with the mini-app. If it is empty, the client derives it from `miniappApi.baseUrl` (`https://host/api/v1` gives `wss://host/api/v1/ws`).
2. The ticket comes from `miniappApi.post("/ws-ticket")`, asked with the admin token. The socket is opened with `?ticket=`.
3. The Studio frame is sandboxed: the browser sends `Origin: null`, which the API accepts. The frame may connect to `wsBackendUrl` (the Studio adds its origin to the `connect-src` of the frame).
4. The client reconnects by itself: 1 s, 2 s, 4 s ... 30 s, with jitter, and asks a new ticket each time.
5. It sends a ping every 60 s, so the API does not close the socket after 5 minutes of silence.
6. The page shows the state: a chip "Realtime: connected / connecting / reconnecting / offline", the number of events, the time of the last one and the last lines of a log. If you see "connected" but the figures do not move, the log shows whether events arrive.

The development page (`npm run dev` in `plugin/`) gives the same host: `wsBackendUrl` is the page origin with `/api/v1/ws`, and the Vite proxy forwards the WebSocket (`ws: true` in `vite.dev.config.ts`).

## Several replicas

`RealtimeHub.publish(message)` sends to the sockets of the process and publishes the message on the cache channel `<CACHE_KEY_PREFIX>realtime`. Each process listens to that channel (started in the lifespan of `app/main.py`) and sends what it receives to its own sockets. A message carries the id of the process that published it, so nobody gets it twice.
- Without `CACHE_URL` there is no bus: one process, the hub is enough.
- A cache that fails never fails a request. The publisher logs a warning. The listener retries with a growing pause (1 s to 30 s).
- If the cache user has no right on pub/sub channels, publishing fails with a warning in the API log and the replicas no longer hear each other. Ask for the right on the channels that start with your prefix.

## An existing project takes the live counters

A project made before 2026-11-25 keeps its own copy of the template. To get the live counters, copy these files from the template (`git show <template commit>:<path>`, or the template repository) and merge the changed ones by hand:
- New: `api/app/services/realtime_bus.py`, `api/tests/test_realtime_events.py`, `miniapp/src/lib/demoEvents.ts`, `miniapp/src/hooks/useDemoLive.ts`, `dev-tools/demoEvents.test.ts`, `plugin/src/lib/realtimeClient.ts`, `plugin/src/hooks/useRealtime.ts`, `plugin/src/features/demo/RealtimeStatus.tsx`, `plugin/src/features/demo/realtimeEvents.ts`, `plugin/dev/realtime.test.ts`.
- Changed: `api/app/services/realtime_service.py` (bus, `publish`, event builders), `api/app/main.py` (bus and its listener in the lifespan), `api/app/api/routes/demo.py` (`async def`, push, `GET /demo/counters`), `api/app/schemas/demo.py` (`DemoCounters`), `miniapp/src/services/demoService.ts` (`readDemoCounters`), `miniapp/src/features/home/DemoDataCard.tsx`, `plugin/src/features/demo/DemoPage.tsx`, `plugin/dev/main.tsx` and `plugin/dev/devHost.ts` (`wsBackendUrl`), `plugin/vite.dev.config.ts` (`ws: true`), and the `test` scripts of `miniapp/package.json` and `plugin/package.json`.
- Then run `cd api && uv run pytest`, `cd miniapp && npm test`, `cd plugin && npm test`.

## Rules

- The SDK client only listens: it has no `send`. A mini-app talks to its API with HTTP (`createApiService`). The ping demo opens its own small socket (`pingClient.ts`) because it must send.
- The address of the socket is `wss://api.<mini-app>.app.<domain>/api/v1/ws`, given by the platform (`docs/web-launcher.md`). Never write it in the code. `createWsService({ api: apiClient })` reads it live.
- The route `/ws` is a public broadcast channel: anyone who knows the address can listen, and no cookie or token is read. Push only what every member may see (counters, "something changed, reload"). Never push a secret or personal data.
- The upgrade checks the `Origin` header, because browsers do not apply CORS to a WebSocket. Accepted: no `Origin` (a script or a native app), `null` (the sandboxed frame of the web launcher, on purpose), an origin of `cors.allowed_origins`, the site that serves the API (its `Origin` host equals the `Host` header, as behind a Coder URL), and a local host in development. Any other website is refused. This keeps casual pages out. It is not authentication.
- The route answers a ping and drops everything else a client sends. A frame over 1024 bytes (counted in bytes, text or binary) closes the socket with code 1009. A socket that sends nothing for 5 minutes is closed: send a ping from time to time to stay. One client address may hold 10 sockets.
- Keep messages small and JSON. Let the mini-app reload data with an HTTP call after a ping: the call is authenticated, the ping is not.
- The hub lives in the memory of one process. Push with `hub.publish`, not `hub.broadcast`: `publish` also reaches the other replicas through the cache ("Several replicas").
- A socket that sends nothing for 5 minutes is closed. The SDK client of the mini-app sends nothing, so it reconnects now and then: read the data again when the socket opens (`onStatusChange`).
- Outside the Up shell (a browser tab in development), `createWsService` refuses to connect without a token unless you pass `requireAuth: false`. The demo does. Inside the shell it asks a ticket either way.
- `POST /demo/broadcast` is an example, served outside production only. Delete it with the rest of the demo before you ship.

## In development (Coder workspace)

- `miniapp/.env` sets `VITE_BACKEND_URL=/api/v1`. The page and the API share one address: Vite proxies `/api/` to the API, WebSocket included (`ws: true` in `vite.config.ts`).
- `miniapp/src/lib/devWsUrl.ts` turns that address into `wss://<same host>/api/v1/ws` (or `ws://` on localhost). It is only the last fallback: in a deployed app the platform address always wins.
- The API accepts an `Origin` equal to its own `Host` (the Coder URL of the page), so the proxied socket is not refused.
- The screens that use the demo routes (`/api/v1/demo`, `/api/v1/demo/broadcast`) call nothing in a production build: `isDemoAvailable()` in `miniapp/src/services/demoService.ts` is false there, and the screen shows "Les routes de démo ne sont servies qu'en développement". Replace those routes with your own before you ship.
- If the screen says "Temps réel non configuré", check that `VITE_BACKEND_URL` in `miniapp/.env` is set (copy `.env.template`) and restart `npm run dev`.

## Tickets

A browser cannot set an `Authorization` header on a WebSocket. The mini-app asks for a ticket with its Hub token, then opens the socket with the ticket in the query string.

1. `createWsService({ api: apiClient })` calls `POST /api/v1/ws-ticket` (its default `ticketPath` is `/ws-ticket`) inside the Up shell. The call carries the scoped Hub token like every route.
2. The API stores a random 256-bit ticket in the mini-app's cache under `<CACHE_KEY_PREFIX>ws-ticket:<ticket>` with a 30-second lifetime, and answers `{ "ticket", "expiresIn" }`.
3. The client opens `/api/v1/ws?ticket=<ticket>`.
4. The socket route redeems the ticket with `GETDEL`: it is read and deleted in one step, so it works once. An unknown, used or expired ticket closes the socket with code 1008 before the upgrade. If the cache cannot be reached, the socket is closed with code 1013 and `POST /ws-ticket` answers 503 (`service_unavailable`).
5. Without a cache (`CACHE_URL` empty), an in-memory store takes over. It is per process: fine for one development server, not for several replicas.

Rules:
- The ticket is a bearer secret for 30 seconds. Never log it. The query string is the only place it goes.
- The socket is public by default. By default (`realtime.require_ticket = false`) it accepts a connection without a ticket. A ticket, when sent, must be valid. Nothing forces a client to ask for one.
- To make the ticket mandatory, set `REALTIME_REQUIRE_TICKET=true` (or `require_ticket = true` under `[realtime]` in `api/configs/config.toml`). A socket without a valid ticket is then refused with code 1008. This only authenticates who opens the socket. The route still broadcasts to every socket and does not keep the user the ticket was issued to. A private channel also needs routing by user in `realtime_socket` (use the value `TicketService.redeem` returns).
- A ticket carries the user (`sub`) and the admin flag it was issued for. `TicketService.redeem` returns them.
- Outside the shell (a browser tab), the SDK uses `devToken` as a `token` query parameter instead. This API ignores it: use the ticket route.

## Channel mode (rooms)

For a room or a group, create the service with `channelField` (for example `groupUuid`). The client sends `{ "action": "subscribe", "groupUuid": "<id>" }` and the server must route messages to the sockets of that room. Authenticate the socket first with a ticket (see "Tickets"): set `REALTIME_REQUIRE_TICKET=true`, and route messages by the user the ticket was issued to. This template ships the broadcast mode only. The SDK README describes the wire protocol.

## Tests

`api/tests/test_ws_ticket.py` covers the ticket route (signed in, 401), a ticket that opens the socket once, an unknown ticket (1008), the in-memory store (single use, expiry, the cap of 1000 tickets), the Redis store with a fake client (prefix, lifetime, `GETDEL`), the service (round trip, corrupt payloads), a cache failure (503 on the route, 1013 on the socket) and `REALTIME_REQUIRE_TICKET`. `api/tests/test_realtime_events.py` covers the two events (every socket gets them, a failed or refused call pushes nothing), `GET /demo/counters`, `hub.publish`, a failing bus and the Redis bus with a fake client. The plugin client (backoff, ticket, ping, stop, parsing) is tested in `plugin/dev/realtime.test.ts` (`cd plugin && npm test`, 22 tests) and the mini-app counters in `dev-tools/demoEvents.test.ts` (`cd miniapp && npm test`). `api/tests/test_realtime.py` covers the broadcast to several sockets, the pong to the sender only, the ping id rules and the ping rate limit, no listener, a socket that leaves, an oversized client message (closed with 1009) and the limits of the hub. Run `cd api && uv run pytest`. The ping client is tested in `dev-tools/pingClient.test.ts` (`cd miniapp && npm test`).
