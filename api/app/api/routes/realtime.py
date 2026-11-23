from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from app.api.deps import RealtimeHubDep
from app.schemas.realtime import BroadcastRequest, BroadcastResult

router = APIRouter(tags=["realtime"])

# What a mini-app may send up the socket: nothing useful.
# The SDK client only listens. Anything sent is read and dropped.
MAX_CLIENT_MESSAGE = 1024


@router.websocket("/ws")
async def realtime_socket(websocket: WebSocket) -> None:
    """Broadcast channel: every connected mini-app receives what the API pushes.

    Public on purpose, like a live feed of counters: push only data every member
    may see, never a secret. For a private channel, ask the client for a ticket
    first (see ``docs/realtime.md``).
    """
    hub = websocket.app.state.realtime_hub
    await websocket.accept()
    if not hub.add(websocket):
        await websocket.close(code=status.WS_1013_TRY_AGAIN_LATER)
        return
    try:
        while True:
            message = await websocket.receive_text()
            if len(message) > MAX_CLIENT_MESSAGE:
                await websocket.close(code=status.WS_1009_MESSAGE_TOO_BIG)
                return
    except WebSocketDisconnect:
        pass
    finally:
        hub.remove(websocket)


# The example that pushes. Mounted only outside production (app/main.py),
# like the demo of the DEV resources.
demo_router = APIRouter(tags=["demo", "realtime"])


@demo_router.post("/demo/broadcast", summary="Push a message to every open socket")
async def broadcast(body: BroadcastRequest, hub: RealtimeHubDep) -> BroadcastResult:
    delivered = await hub.broadcast({"event": "demo_message", "text": body.text})
    return BroadcastResult(delivered=delivered)
