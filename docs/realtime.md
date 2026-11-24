# Realtime: the WebSocket of your API

The API pushes, the mini-app listens. Typical use: a person reacts, the API stores it and tells every other open mini-app. Last audited: 2026-11-24.

## The pieces

| Piece | File | Role |
| --- | --- | --- |
| Socket route | `api/app/api/routes/realtime.py`, `GET /api/v1/ws` (WebSocket) | Accepts connections, keeps them in the hub, drops them when they leave. |
| Hub | `api/app/services/realtime_service.py` (`RealtimeHub`) | Holds the open sockets (200 at most, 10 per client address) and broadcasts a message to all of them at once. A socket that fails or does not read within 2 seconds is dropped and closed. |
| Ticket route | `api/app/api/routes/realtime.py`, `POST /api/v1/ws-ticket`; `api/app/services/ticket_service.py` | Signed in (scoped Hub token). Returns `{ "ticket": "...", "expiresIn": 30 }`. See "Tickets". |
| Push example | `POST /api/v1/demo/broadcast` (development only, signed-in member) | Body `{ "text": "..." }`. Pushes `{ "event": "demo_message", "text": "..." }` to every open socket. |
| Client | `miniapp/src/features/tools/RealtimeDemo.tsx` | `createWsService` in broadcast mode. Shows the status and the messages received. |
| Ping client | `miniapp/src/lib/pingClient.ts` | A small socket to the same address that sends `ping` and shows the `pong` with the round trip. |

Run both servers, open the screen **Outils** then **Temps réel**, press **Envoyer un message à tous**: the message goes to the API with HTTP and comes back through the socket.

Press **Ping** to see the socket work in both directions:

1. The mini-app sends `{ "type": "ping", "id": 1 }` over the socket.
2. The API answers `{ "type": "pong", "id": 1, "serverTime": "<ISO 8601>" }` to THAT socket only. It is not a broadcast.
3. The screen shows `Pong #1 reçu en 12 ms` and a log of the last messages. The badge says `connecté` or `déconnecté`.

The round trip is measured by the mini-app with its own clock. The `id` is a small integer chosen by the client to match the pong. A socket may ping 5 times per second: more are dropped without an answer.

## Rules

- The SDK client only listens: it has no `send`. A mini-app talks to its API with HTTP (`createApiService`). The ping demo opens its own small socket (`pingClient.ts`) because it must send.
- The address of the socket is `wss://api.<mini-app>.app.<domain>/api/v1/ws`, given by the platform (`docs/web-launcher.md`). Never write it in the code. `createWsService({ api: apiClient })` reads it live.
- The route `/ws` is a public broadcast channel: anyone who knows the address can listen, and no cookie or token is read. Push only what every member may see (counters, "something changed, reload"). Never push a secret or personal data.
- The upgrade checks the `Origin` header, because browsers do not apply CORS to a WebSocket. Accepted: no `Origin` (a script or a native app), `null` (the sandboxed frame of the web launcher, on purpose), an origin of `cors.allowed_origins`, the site that serves the API (its `Origin` host equals the `Host` header, as behind a Coder URL), and a local host in development. Any other website is refused. This keeps casual pages out. It is not authentication.
- The route answers a ping and drops everything else a client sends. A frame over 1024 bytes (counted in bytes, text or binary) closes the socket with code 1009. A socket that sends nothing for 5 minutes is closed: send a ping from time to time to stay. One client address may hold 10 sockets.
- Keep messages small and JSON. Let the mini-app reload data with an HTTP call after a ping: the call is authenticated, the ping is not.
- The hub lives in the memory of one process. With several replicas of the API, each replica only reaches its own sockets. Use the cache (Valkey publish and subscribe, keys and channels start with `CACHE_KEY_PREFIX`) to fan out between replicas.
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
4. The socket route redeems the ticket with `GETDEL`: it is read and deleted in one step, so it works once. An unknown, used or expired ticket closes the socket with code 1008 before the upgrade.
5. Without a cache (`CACHE_URL` empty), an in-memory store takes over. It is per process: fine for one development server, not for several replicas.

Rules:
- The ticket is a bearer secret for 30 seconds. Never log it. The query string is the only place it goes.
- In this template the socket still accepts a connection without a ticket: the broadcast channel is public. A ticket, when present, must be valid. For a private channel, refuse a socket without a ticket in `realtime_socket`.
- A ticket carries the user (`sub`) and the admin flag it was issued for. `TicketService.redeem` returns them.
- Outside the shell (a browser tab), the SDK uses `devToken` as a `token` query parameter instead. This API ignores it: use the ticket route.

## Channel mode (rooms)

For a room or a group, create the service with `channelField` (for example `groupUuid`). The client sends `{ "action": "subscribe", "groupUuid": "<id>" }` and the server must route messages to the sockets of that room. Authenticate the socket first with a ticket (see "Tickets"): make it mandatory in `realtime_socket`, and route messages by the user the ticket was issued to. This template ships the broadcast mode only. The SDK README describes the wire protocol.

## Tests

`api/tests/test_ws_ticket.py` covers the ticket route (signed in, 401, other audience), a ticket that opens the socket once, an unknown ticket (1008), the service, the expiry and the Redis store (prefix, lifetime, `GETDEL`). `api/tests/test_realtime.py` covers the broadcast to several sockets, the pong to the sender only, the ping id rules and the ping rate limit, no listener, a socket that leaves, an oversized client message (closed with 1009) and the limits of the hub. Run `cd api && uv run pytest`. The ping client is tested in `dev-tools/pingClient.test.ts` (`cd miniapp && npm test`).
