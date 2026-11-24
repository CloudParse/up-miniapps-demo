import asyncio
import json
import time
from datetime import UTC, datetime

from fastapi import APIRouter, WebSocket, status
from starlette.concurrency import run_in_threadpool

from app.api.deps import CurrentUserDep, RealtimeHubDep, TicketServiceDep
from app.schemas.realtime import BroadcastRequest, BroadcastResult
from app.schemas.ws_ticket import WsTicket
from app.services.ticket_service import TICKET_TTL_SECONDS

router = APIRouter(tags=["realtime"])

# What a mini-app may send up the socket: a ping (``{"type": "ping", "id": 1}``),
# answered to the sender only with a pong. Anything else is read and dropped.
# The cap is in BYTES of the frame, text or binary.
MAX_CLIENT_MESSAGE_BYTES = 1024
# A socket that sends nothing for this long is closed. A client may send a ping to stay.
IDLE_TIMEOUT_SECONDS = 300.0
# A socket may ping this many times per second.
# More are read and dropped without an answer.
MAX_PINGS_PER_SECOND = 5
# The web launcher runs a mini-app in a sandboxed frame: the browser sends this Origin.
SANDBOX_ORIGIN = "null"


def client_address(websocket: WebSocket) -> str:
    """The address of the client behind the platform's proxy (Traefik).

    The proxy appends the real peer at the END of X-Forwarded-For: the last entry is
    the one a client cannot forge. Without the header (a direct connection in
    development) it is the peer of the connection.
    """
    forwarded = websocket.headers.get("x-forwarded-for", "")
    last = forwarded.rsplit(",", 1)[-1].strip()
    if last:
        return last
    return websocket.client.host if websocket.client else ""


def origin_allowed(websocket: WebSocket, allowed: list[str], development: bool) -> bool:
    """Browsers do not apply CORS to a WebSocket: the upgrade checks the Origin itself.

    No Origin header (a native app or a script) is accepted: this channel is public
    and carries no cookie. An Origin must be the sandbox frame of the web launcher
    ("null"), a configured origin, the site that serves this very API (its Origin host
    equals the Host header: the Vite dev proxy behind a Coder URL), or a local host in
    development.
    """
    origin = websocket.headers.get("origin")
    if origin is None or origin == SANDBOX_ORIGIN or origin in allowed:
        return True
    host = websocket.headers.get("host")
    if host and origin.split("://", 1)[-1] == host:
        return True
    if development:
        host = origin.removeprefix("http://")
        return origin.startswith("http://") and host.split(":")[0] in (
            "localhost",
            "127.0.0.1",
        )
    return False


async def ticket_allowed(websocket: WebSocket) -> bool:
    """``True`` without a ``ticket`` parameter; with one, only if it is redeemed now."""
    ticket = websocket.query_params.get("ticket")
    if ticket is None:
        return True
    service = websocket.app.state.ticket_service
    return await run_in_threadpool(service.redeem, ticket) is not None


def ping_id(text: str | None) -> tuple[bool, int | None]:
    """Whether the text frame is a ping, and its id.

    The id is a small integer the client uses to match the pong.
    """
    if not text:
        return False, None
    try:
        data = json.loads(text)
    except ValueError:
        return False, None
    if not isinstance(data, dict) or data.get("type") != "ping":
        return False, None
    raw = data.get("id")
    ident = raw if isinstance(raw, int) and not isinstance(raw, bool) else None
    return True, ident if ident is not None and 0 <= ident < 2**31 else None


@router.websocket("/ws")
async def realtime_socket(websocket: WebSocket) -> None:
    """Broadcast channel: every connected mini-app receives what the API pushes.

    Public on purpose, like a live feed of counters: push only data every member
    may see, never a secret. Any website may open it (an Origin is checked, a cookie
    is not used), so it must carry nothing private. A ``ticket`` query parameter
    (from ``POST /ws-ticket``) is checked when present: an unknown, used or expired
    ticket refuses the socket. For a private channel, make the ticket mandatory and
    route by ``user`` (see ``docs/realtime.md``).
    """
    state = websocket.app.state
    hub = state.realtime_hub
    config = state.config
    if not origin_allowed(
        websocket, config.cors.allowed_origins, config.is_development
    ):
        # Before accept(): the upgrade is refused with a 403.
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    if not await ticket_allowed(websocket):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    await websocket.accept()
    if not hub.add(websocket, client_address(websocket)):
        await websocket.close(code=status.WS_1013_TRY_AGAIN_LATER)
        return
    recent_pings: list[float] = []
    try:
        while True:
            try:
                frame = await asyncio.wait_for(
                    websocket.receive(), IDLE_TIMEOUT_SECONDS
                )
            except TimeoutError:
                await websocket.close(code=status.WS_1001_GOING_AWAY)
                return
            if frame["type"] == "websocket.disconnect":
                return
            size = len(frame.get("bytes") or b"") or len(
                (frame.get("text") or "").encode()
            )
            if size > MAX_CLIENT_MESSAGE_BYTES:
                await websocket.close(code=status.WS_1009_MESSAGE_TOO_BIG)
                return
            is_ping, ident = ping_id(frame.get("text"))
            if is_ping:
                now = time.monotonic()
                recent_pings[:] = [t for t in recent_pings if now - t < 1.0]
                if len(recent_pings) < MAX_PINGS_PER_SECOND:
                    recent_pings.append(now)
                    # To THIS socket only: a pong is not a broadcast.
                    await websocket.send_json(
                        {
                            "type": "pong",
                            "id": ident,
                            "serverTime": datetime.now(UTC).isoformat(),
                        }
                    )
    finally:
        hub.remove(websocket)


@router.post("/ws-ticket", summary="Get a single-use ticket to open the WebSocket")
async def create_ws_ticket(user: CurrentUserDep, tickets: TicketServiceDep) -> WsTicket:
    """Signed in with the scoped Hub token, like every route. The SDK client
    (``createWsService``) calls this path before it opens ``/ws``."""
    ticket = await run_in_threadpool(tickets.issue, user)
    return WsTicket(ticket=ticket, expires_in=TICKET_TTL_SECONDS)


# The example that pushes. Mounted only outside production (app/main.py),
# like the demo of the DEV resources. A signed-in member only, even in development.
demo_router = APIRouter(tags=["demo", "realtime"])


@demo_router.post("/demo/broadcast", summary="Push a message to every open socket")
async def broadcast(
    body: BroadcastRequest, hub: RealtimeHubDep, _: CurrentUserDep
) -> BroadcastResult:
    delivered = await hub.broadcast({"event": "demo_message", "text": body.text})
    return BroadcastResult(delivered=delivered)
