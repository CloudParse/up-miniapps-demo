"""Short-lived, single-use tickets that open a WebSocket.

A browser cannot set an ``Authorization`` header on a WebSocket. The mini-app asks
``POST /api/v1/ws-ticket`` (signed in with its Hub token), gets a random ticket and
opens ``/api/v1/ws?ticket=<ticket>``. The socket route redeems the ticket once.

The ticket lives in the mini-app's cache (Redis) under its key prefix. Without a
cache (no ``CACHE_URL``: a bare local run) an in-memory store takes over. That store
is per process, so it is fine for one development server only.
"""

from __future__ import annotations

import json
import secrets
import threading
import time
from typing import Protocol
from uuid import UUID

import redis

from app.core.config import Config
from app.core.security import AuthenticatedUser

# Long enough for the client to open the socket right after the request.
TICKET_TTL_SECONDS = 30
TIMEOUT_SECONDS = 5
# 32 random bytes: not guessable, URL safe.
TICKET_BYTES = 32
# The in-memory store forgets expired tickets; this caps what it keeps meanwhile.
MEMORY_MAX_TICKETS = 1000


class TicketStore(Protocol):
    def put(self, ticket: str, payload: str, ttl_seconds: int) -> None: ...

    def take(self, ticket: str) -> str | None:
        """Return the payload and delete it in one step, or ``None``."""
        ...


class RedisTicketStore:
    def __init__(self, url: str, key_prefix: str) -> None:
        self._url = url
        self._prefix = key_prefix

    def _client(self) -> redis.Redis:
        return redis.Redis.from_url(
            self._url,
            socket_connect_timeout=TIMEOUT_SECONDS,
            socket_timeout=TIMEOUT_SECONDS,
            decode_responses=True,
        )

    def _key(self, ticket: str) -> str:
        # Under the mini-app's prefix: the cache user may touch nothing else.
        return f"{self._prefix}ws-ticket:{ticket}"

    def put(self, ticket: str, payload: str, ttl_seconds: int) -> None:
        client = self._client()
        try:
            client.set(self._key(ticket), payload, ex=ttl_seconds)
        finally:
            client.close()

    def take(self, ticket: str) -> str | None:
        client = self._client()
        try:
            # GETDEL reads and deletes atomically: two sockets cannot redeem it.
            value = client.getdel(self._key(ticket))
        finally:
            client.close()
        return str(value) if value is not None else None


class MemoryTicketStore:
    def __init__(self) -> None:
        self._items: dict[str, tuple[float, str]] = {}
        self._lock = threading.Lock()

    def put(self, ticket: str, payload: str, ttl_seconds: int) -> None:
        now = time.monotonic()
        with self._lock:
            self._items = {k: v for k, v in self._items.items() if v[0] > now}
            if len(self._items) >= MEMORY_MAX_TICKETS:
                self._items.pop(next(iter(self._items)))
            self._items[ticket] = (now + ttl_seconds, payload)

    def take(self, ticket: str) -> str | None:
        with self._lock:
            item = self._items.pop(ticket, None)
        if item is None or item[0] <= time.monotonic():
            return None
        return item[1]


def build_ticket_store(config: Config) -> TicketStore:
    url = config.cache.url.get_secret_value()
    if url:
        return RedisTicketStore(url, config.cache.key_prefix)
    return MemoryTicketStore()


class TicketService:
    def __init__(self, store: TicketStore) -> None:
        self._store = store

    def issue(self, user: AuthenticatedUser) -> str:
        ticket = secrets.token_urlsafe(TICKET_BYTES)
        payload = json.dumps({"sub": str(user.user_uuid), "admin": user.is_admin})
        self._store.put(ticket, payload, TICKET_TTL_SECONDS)
        return ticket

    def redeem(self, ticket: str) -> AuthenticatedUser | None:
        """The user the ticket was issued to, once.

        ``None`` if the ticket is unknown, used or expired.
        """
        raw = self._store.take(ticket)
        if raw is None:
            return None
        try:
            data = json.loads(raw)
            return AuthenticatedUser(
                user_uuid=UUID(data["sub"]), is_admin=bool(data["admin"])
            )
        except ValueError, KeyError, TypeError:
            return None
