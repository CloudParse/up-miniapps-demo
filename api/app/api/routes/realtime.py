import asyncio

from fastapi import APIRouter, WebSocket, status

from app.api.deps import CurrentUserDep, RealtimeHubDep
from app.schemas.realtime import BroadcastRequest, BroadcastResult

router = APIRouter(tags=["realtime"])

# What a mini-app may send up the socket: nothing useful. The SDK client only
# listens, so anything it sends (a ping, at most) is read and dropped.
# The cap is in BYTES of the frame, text or binary.
MAX_CLIENT_MESSAGE_BYTES = 1024
# A socket that sends nothing for this long is closed. A client may send a ping to stay.
IDLE_TIMEOUT_SECONDS = 300.0
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
    ("null"), a configured origin, or a local host in development.
    """
    origin = websocket.headers.get("origin")
    if origin is None or origin == SANDBOX_ORIGIN or origin in allowed:
        return True
    if development:
        host = origin.removeprefix("http://")
        return origin.startswith("http://") and host.split(":")[0] in (
            "localhost",
            "127.0.0.1",
        )
    return False


@router.websocket("/ws")
async def realtime_socket(websocket: WebSocket) -> None:
    """Broadcast channel: every connected mini-app receives what the API pushes.

    Public on purpose, like a live feed of counters: push only data every member
    may see, never a secret. Any website may open it (an Origin is checked, a cookie
    is not used), so it must carry nothing private. For a private channel, add a
    route that asks the client for a ticket first (see ``docs/realtime.md``).
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
    await websocket.accept()
    if not hub.add(websocket, client_address(websocket)):
        await websocket.close(code=status.WS_1013_TRY_AGAIN_LATER)
        return
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
    finally:
        hub.remove(websocket)


# The example that pushes. Mounted only outside production (app/main.py),
# like the demo of the DEV resources. A signed-in member only, even in development.
demo_router = APIRouter(tags=["demo", "realtime"])


@demo_router.post("/demo/broadcast", summary="Push a message to every open socket")
async def broadcast(
    body: BroadcastRequest, hub: RealtimeHubDep, _: CurrentUserDep
) -> BroadcastResult:
    delivered = await hub.broadcast({"event": "demo_message", "text": body.text})
    return BroadcastResult(delivered=delivered)
