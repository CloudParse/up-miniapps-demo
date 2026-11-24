import json
import time
from typing import Any
from uuid import UUID

import pytest
import redis
from fastapi.testclient import TestClient
from pydantic import SecretStr
from starlette.websockets import WebSocketDisconnect

from app.core.config import Config
from app.core.errors import ServiceUnavailableError
from app.core.security import AuthenticatedUser
from app.main import create_app
from app.services.ticket_service import (
    MEMORY_MAX_TICKETS,
    MemoryTicketStore,
    RedisTicketStore,
    TicketService,
    build_ticket_store,
)
from tests.conftest import USER_UUID, TokenFactory

TICKET = "/api/v1/ws-ticket"
SOCKET = "/api/v1/ws"


def _auth(make_token: TokenFactory) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token()}"}


def test_ticket_needs_a_token(client: TestClient) -> None:
    assert client.post(TICKET).status_code == 401


def test_ticket_opens_the_socket_once(
    client: TestClient, make_token: TokenFactory
) -> None:
    response = client.post(TICKET, headers=_auth(make_token))
    assert response.status_code == 200
    ticket = response.json()["ticket"]

    with client.websocket_connect(f"{SOCKET}?ticket={ticket}"):
        pass

    with (
        pytest.raises(WebSocketDisconnect),
        client.websocket_connect(f"{SOCKET}?ticket={ticket}"),
    ):
        pass


def test_unknown_ticket_is_refused(client: TestClient) -> None:
    with (
        pytest.raises(WebSocketDisconnect),
        client.websocket_connect(f"{SOCKET}?ticket=nope"),
    ):
        pass


def test_socket_without_ticket_stays_public(client: TestClient) -> None:
    with client.websocket_connect(SOCKET):
        pass


class _Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> _Clock:
    fake = _Clock()
    monkeypatch.setattr(time, "monotonic", fake)
    return fake


def test_memory_store_gives_a_ticket_once() -> None:
    store = MemoryTicketStore()
    store.put("t", "payload", 30)

    assert store.take("t") == "payload"
    assert store.take("t") is None


def test_memory_store_forgets_an_expired_ticket(clock: _Clock) -> None:
    store = MemoryTicketStore()
    store.put("t", "payload", 30)
    clock.now += 31

    assert store.take("t") is None


def test_memory_store_keeps_a_ticket_until_its_expiry(clock: _Clock) -> None:
    store = MemoryTicketStore()
    store.put("t", "payload", 30)
    clock.now += 29

    assert store.take("t") == "payload"


def test_memory_store_drops_expired_tickets_on_put(clock: _Clock) -> None:
    store = MemoryTicketStore()
    store.put("old", "x", 30)
    clock.now += 31
    store.put("new", "y", 30)

    assert store.take("old") is None
    assert store.take("new") == "y"


def test_memory_store_evicts_the_oldest_ticket_at_the_cap() -> None:
    store = MemoryTicketStore()
    for index in range(MEMORY_MAX_TICKETS):
        store.put(f"t{index}", str(index), 30)
    store.put("extra", "e", 30)

    assert store.take("t0") is None
    assert store.take("t1") == "1"
    assert store.take("extra") == "e"


class _FakeRedis:
    """What ``RedisTicketStore`` uses of a redis client, over a dict."""

    def __init__(self) -> None:
        self.data: dict[str, str] = {}
        self.ttls: dict[str, int] = {}
        self.closed = 0

    def set(self, key: str, value: str, ex: int) -> None:
        self.data[key] = value
        self.ttls[key] = ex

    def getdel(self, key: str) -> str | None:
        return self.data.pop(key, None)

    def close(self) -> None:
        self.closed += 1


@pytest.fixture
def fake_redis(monkeypatch: pytest.MonkeyPatch) -> _FakeRedis:
    fake = _FakeRedis()
    urls: list[tuple[str, dict[str, Any]]] = []

    def from_url(url: str, **options: Any) -> _FakeRedis:
        urls.append((url, options))
        return fake

    monkeypatch.setattr(redis.Redis, "from_url", from_url)
    fake.urls = urls  # type: ignore[attr-defined]
    return fake


def test_redis_store_uses_the_prefix_ttl_and_getdel(fake_redis: _FakeRedis) -> None:
    store = RedisTicketStore("redis://cache:6379/0", "app1:")
    store.put("abc", "payload", 30)

    assert fake_redis.data == {"app1:ws-ticket:abc": "payload"}
    assert fake_redis.ttls == {"app1:ws-ticket:abc": 30}
    assert store.take("abc") == "payload"
    assert store.take("abc") is None
    assert fake_redis.closed == 3


def test_build_ticket_store_picks_redis_when_a_cache_url_is_set(
    config: Config,
) -> None:
    assert isinstance(build_ticket_store(config), MemoryTicketStore)
    with_cache = config.model_copy(
        update={
            "cache": config.cache.model_copy(
                update={"url": SecretStr("redis://cache:6379/0")}
            )
        }
    )
    assert isinstance(build_ticket_store(with_cache), RedisTicketStore)


def test_service_round_trip_gives_the_user_once() -> None:
    service = TicketService(MemoryTicketStore())
    ticket = service.issue(AuthenticatedUser(user_uuid=USER_UUID, is_admin=True))

    assert service.redeem(ticket) == AuthenticatedUser(
        user_uuid=USER_UUID, is_admin=True
    )
    assert service.redeem(ticket) is None


@pytest.mark.parametrize(
    "payload",
    [
        "not json",
        "[]",
        "{}",
        json.dumps({"sub": "not-a-uuid", "admin": False}),
        json.dumps({"sub": str(UUID(int=1))}),
        json.dumps({"sub": 5, "admin": False}),
    ],
)
def test_corrupt_payload_redeems_to_none(payload: str) -> None:
    store = MemoryTicketStore()
    store.put("t", payload, 30)

    assert TicketService(store).redeem("t") is None


class _BrokenStore:
    def put(self, ticket: str, payload: str, ttl_seconds: int) -> None:
        raise redis.ConnectionError("down")

    def take(self, ticket: str) -> str | None:
        raise redis.ConnectionError("down")


def test_service_turns_a_redis_failure_into_service_unavailable() -> None:
    service = TicketService(_BrokenStore())

    with pytest.raises(ServiceUnavailableError):
        service.issue(AuthenticatedUser(user_uuid=USER_UUID, is_admin=False))
    with pytest.raises(ServiceUnavailableError):
        service.redeem("t")


@pytest.fixture
def broken_client(config: Config) -> TestClient:
    app = create_app(config)
    app.state.ticket_service = TicketService(_BrokenStore())
    return TestClient(app)


def test_ticket_route_answers_503_when_the_cache_is_down(
    broken_client: TestClient, make_token: TokenFactory
) -> None:
    response = broken_client.post(TICKET, headers=_auth(make_token))

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"


def test_socket_with_a_ticket_is_refused_when_the_cache_is_down(
    broken_client: TestClient,
) -> None:
    with (
        pytest.raises(WebSocketDisconnect) as refused,
        broken_client.websocket_connect(f"{SOCKET}?ticket=abc"),
    ):
        pass

    assert refused.value.code == 1013


def test_unknown_ticket_is_refused_with_1008(client: TestClient) -> None:
    with (
        pytest.raises(WebSocketDisconnect) as refused,
        client.websocket_connect(f"{SOCKET}?ticket=nope"),
    ):
        pass

    assert refused.value.code == 1008


@pytest.fixture
def strict_client(config: Config) -> TestClient:
    strict = config.model_copy(
        update={"realtime": config.realtime.model_copy(update={"require_ticket": True})}
    )
    return TestClient(create_app(strict))


def test_require_ticket_refuses_a_socket_without_ticket(
    strict_client: TestClient,
) -> None:
    with (
        pytest.raises(WebSocketDisconnect) as refused,
        strict_client.websocket_connect(SOCKET),
    ):
        pass

    assert refused.value.code == 1008


def test_require_ticket_still_accepts_a_valid_ticket(
    strict_client: TestClient, make_token: TokenFactory
) -> None:
    ticket = strict_client.post(TICKET, headers=_auth(make_token)).json()["ticket"]

    with strict_client.websocket_connect(f"{SOCKET}?ticket={ticket}"):
        pass


def test_require_ticket_defaults_to_false(config: Config) -> None:
    assert config.realtime.require_ticket is False
