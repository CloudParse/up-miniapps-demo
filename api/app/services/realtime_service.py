"""Realtime push to the mini-apps that hold a WebSocket open.

This is the broadcast mode of ``createWsService`` in the SDK. The server pushes and
the mini-app listens: an event happens (a REST call, a job), the API calls
``broadcast`` and every connected mini-app receives the message. The SDK client has
no ``send``: a mini-app talks to the API with HTTP.

This module knows nothing about FastAPI routes. It only needs objects with an async
``send_json``.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Protocol

# One API process keeps every connection in memory. A limit stops a flood of sockets.
MAX_CONNECTIONS = 200
# One client address may hold only a few of them, so one host cannot lock everybody out.
MAX_CONNECTIONS_PER_CLIENT = 10
# A client that does not read stops accepting data: its send must not hold the rest.
SEND_TIMEOUT_SECONDS = 2.0


class Socket(Protocol):
    async def send_json(self, data: object) -> None: ...

    async def close(self, code: int = 1000) -> None: ...


class RealtimeHub:
    """The sockets that are open right now, and a broadcast to all of them."""

    def __init__(
        self,
        max_connections: int = MAX_CONNECTIONS,
        max_per_client: int = MAX_CONNECTIONS_PER_CLIENT,
        send_timeout: float = SEND_TIMEOUT_SECONDS,
    ) -> None:
        self._sockets: list[Socket] = []
        self._clients: dict[int, str] = {}
        self._max = max_connections
        self._max_per_client = max_per_client
        self._send_timeout = send_timeout

    @property
    def count(self) -> int:
        return len(self._sockets)

    def add(self, socket: Socket, client: str = "") -> bool:
        """Register a socket. ``False`` when the hub or the client is full."""
        if len(self._sockets) >= self._max:
            return False
        if (
            client
            and list(self._clients.values()).count(client) >= self._max_per_client
        ):
            return False
        self._sockets.append(socket)
        if client:
            self._clients[id(socket)] = client
        return True

    def remove(self, socket: Socket) -> None:
        if socket in self._sockets:
            self._sockets.remove(socket)
        self._clients.pop(id(socket), None)

    async def broadcast(self, message: dict[str, object]) -> int:
        """Send ``message`` to every open socket and return how many got it.

        The sends run together, each with a timeout. A socket that fails or does not
        read in time is dropped and closed. It must not stop or slow the others.
        """
        sockets = list(self._sockets)
        results = await asyncio.gather(
            *(self._send(socket, message) for socket in sockets)
        )
        return sum(results)

    async def _send(self, socket: Socket, message: dict[str, object]) -> bool:
        try:
            await asyncio.wait_for(socket.send_json(message), self._send_timeout)
        except Exception:  # a closed, broken or stalled socket
            self.remove(socket)
            with contextlib.suppress(Exception):  # already gone
                await asyncio.wait_for(socket.close(), self._send_timeout)
            return False
        return True
