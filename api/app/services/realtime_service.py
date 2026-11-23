"""Realtime push to the mini-apps that hold a WebSocket open.

This is the broadcast mode of ``createWsService`` in the SDK. The server pushes and
the mini-app listens: an event happens (a REST call, a job), the API calls
``broadcast`` and every connected mini-app receives the message. The SDK client has
no ``send``: a mini-app talks to the API with HTTP.

This module knows nothing about FastAPI routes. It only needs objects with an async
``send_json``.
"""

from __future__ import annotations

from typing import Protocol

# One API process keeps every connection in memory. A limit stops a flood of sockets.
MAX_CONNECTIONS = 200


class Socket(Protocol):
    async def send_json(self, data: object) -> None: ...


class RealtimeHub:
    """The sockets that are open right now, and a broadcast to all of them."""

    def __init__(self, max_connections: int = MAX_CONNECTIONS) -> None:
        self._sockets: list[Socket] = []
        self._max = max_connections

    @property
    def count(self) -> int:
        return len(self._sockets)

    def add(self, socket: Socket) -> bool:
        """Register a socket. ``False`` when the hub is full: refuse the socket."""
        if len(self._sockets) >= self._max:
            return False
        self._sockets.append(socket)
        return True

    def remove(self, socket: Socket) -> None:
        if socket in self._sockets:
            self._sockets.remove(socket)

    async def broadcast(self, message: dict[str, object]) -> int:
        """Send ``message`` to every open socket and return how many got it.

        A socket that fails is dropped. It must not stop the others.
        """
        delivered = 0
        for socket in list(self._sockets):
            try:
                await socket.send_json(message)
            except Exception:  # a closed or broken socket
                self.remove(socket)
            else:
                delivered += 1
        return delivered
