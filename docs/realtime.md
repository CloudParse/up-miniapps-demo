# Realtime: the WebSocket of your API

The API pushes, the mini-app listens. Typical use: a person reacts, the API stores it and tells every other open mini-app. Last audited: 2026-11-23.

## The pieces

| Piece | File | Role |
| --- | --- | --- |
| Socket route | `api/app/api/routes/realtime.py`, `GET /api/v1/ws` (WebSocket) | Accepts connections, keeps them in the hub, drops them when they leave. |
| Hub | `api/app/services/realtime_service.py` (`RealtimeHub`) | Holds the open sockets (200 at most, 10 per client address) and broadcasts a message to all of them at once. A socket that fails or does not read within 2 seconds is dropped and closed. |
| Push example | `POST /api/v1/demo/broadcast` (development only, signed-in member) | Body `{ "text": "..." }`. Pushes `{ "event": "demo_message", "text": "..." }` to every open socket. |
| Client | `miniapp/src/features/tools/RealtimeDemo.tsx` | `createWsService` in broadcast mode. Shows the status and the messages received. |

Run both servers, open the screen **Outils** then **Temps réel**, press **Envoyer un message à tous**: the message goes to the API with HTTP and comes back through the socket.

## Rules

- The SDK client only listens: it has no `send`. A mini-app talks to its API with HTTP (`createApiService`).
- The address of the socket is `wss://api.<mini-app>.app.<domain>/api/v1/ws`, given by the platform (`docs/web-launcher.md`). Never write it in the code. `createWsService({ api: apiClient })` reads it live.
- The route `/ws` is a public broadcast channel: anyone who knows the address can listen, and no cookie or token is read. Push only what every member may see (counters, "something changed, reload"). Never push a secret or personal data.
- The upgrade checks the `Origin` header, because browsers do not apply CORS to a WebSocket. Accepted: no `Origin` (a script or a native app), `null` (the sandboxed frame of the web launcher, on purpose), an origin of `cors.allowed_origins`, and a local host in development. Any other website is refused. This keeps casual pages out. It is not authentication.
- The route reads and drops what a client sends. A frame over 1024 bytes (counted in bytes, text or binary) closes the socket with code 1009. A socket that sends nothing for 5 minutes is closed: send a ping from time to time to stay. One client address may hold 10 sockets.
- Keep messages small and JSON. Let the mini-app reload data with an HTTP call after a ping: the call is authenticated, the ping is not.
- The hub lives in the memory of one process. With several replicas of the API, each replica only reaches its own sockets. Use the cache (Valkey publish and subscribe, keys and channels start with `CACHE_KEY_PREFIX`) to fan out between replicas.
- `POST /demo/broadcast` is an example, served outside production only. Delete it with the rest of the demo before you ship.

## Channel mode (rooms)

For a room or a group, create the service with `channelField` (for example `groupUuid`). The client sends `{ "action": "subscribe", "groupUuid": "<id>" }` and the server must route messages to the sockets of that room. Authenticate the socket first: add a route like `POST /api/v1/ws-ticket` (not in this template) (signed in) for a short-lived ticket, and check it when the socket opens. This template ships the broadcast mode only. The SDK README describes the wire protocol.

## Tests

`api/tests/test_realtime.py` covers the broadcast to several sockets, no listener, a socket that leaves, an oversized client message (closed with 1009) and the limits of the hub. Run `cd api && uv run pytest`.
