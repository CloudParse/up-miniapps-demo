"""The events the demo pushes (docs/realtime.md) and the shared bus."""

import asyncio
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.config import Config
from app.main import create_app
from app.services import realtime_bus
from app.services.demo_admin_service import DemoAdminActions
from app.services.demo_service import DemoActions
from app.services.realtime_bus import RedisRealtimeBus, decode, encode
from app.services.realtime_service import RealtimeHub
from tests.conftest import TokenFactory

VISIT = "/api/v1/demo/visit"
RESET = "/api/v1/admin/demo/reset-cache"
COUNTERS = "/api/v1/demo/counters"


def _auth(make_token: TokenFactory, *, admin: bool = False) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(admin=admin)}"}


def _fake_resources(client: TestClient) -> None:
    state: dict[str, Any] = {"database": 0, "cache": 0}

    def database(_user: str) -> int:
        state["database"] += 1
        return int(state["database"])

    def cache(_user: str) -> int:
        state["cache"] += 1
        return int(state["cache"])

    def reset() -> None:
        state["cache"] = 0

    client.app.state.demo_actions = DemoActions(  # type: ignore[attr-defined]
        database=database, cache=cache, storage=None
    )
    client.app.state.demo_admin_actions = DemoAdminActions(  # type: ignore[attr-defined]
        database_visits=lambda: int(state["database"]),
        cache_visits=lambda: int(state["cache"]),
        storage_objects=None,
        reset_cache_visits=reset,
    )


def test_a_visit_is_pushed_to_every_open_socket(
    client: TestClient, make_token: TokenFactory
) -> None:
    _fake_resources(client)
    with (
        client.websocket_connect("/api/v1/ws") as plugin,
        client.websocket_connect("/api/v1/ws") as miniapp,
    ):
        response = client.post(VISIT, headers=_auth(make_token))

        assert response.json()["cacheVisits"] == 1
        for socket in (plugin, miniapp):
            event = socket.receive_json()
            assert event["event"] == "visit_recorded"
            assert event["databaseVisits"] == 1
            assert event["cacheVisits"] == 1
            assert isinstance(event["at"], str)


def test_a_reset_is_pushed_to_every_open_socket(
    client: TestClient, make_token: TokenFactory
) -> None:
    _fake_resources(client)
    client.post(VISIT, headers=_auth(make_token))
    with (
        client.websocket_connect("/api/v1/ws") as plugin,
        client.websocket_connect("/api/v1/ws") as miniapp,
    ):
        response = client.post(RESET, headers=_auth(make_token, admin=True))

        assert response.json()["cacheVisits"] == 0
        for socket in (plugin, miniapp):
            event = socket.receive_json()
            assert event["event"] == "counter_reset"
            assert event["cacheVisits"] == 0


def test_a_refused_reset_pushes_nothing(
    client: TestClient, make_token: TokenFactory
) -> None:
    _fake_resources(client)
    with client.websocket_connect("/api/v1/ws") as socket:
        assert client.post(RESET, headers=_auth(make_token)).status_code == 403
        # The next push is the visit: nothing was queued before it.
        client.post(VISIT, headers=_auth(make_token))
        assert socket.receive_json()["event"] == "visit_recorded"


def test_a_failed_visit_pushes_nothing(
    client: TestClient, make_token: TokenFactory
) -> None:
    def broken(_user: str) -> int:
        raise ConnectionError("db refused")

    client.app.state.demo_actions = DemoActions(  # type: ignore[attr-defined]
        database=broken, cache=None, storage=None
    )
    quiet = TestClient(client.app, raise_server_exceptions=False)
    with client.websocket_connect("/api/v1/ws") as socket:
        assert quiet.post(VISIT, headers=_auth(make_token)).status_code == 500
        _fake_resources(client)
        client.post(VISIT, headers=_auth(make_token))
        assert socket.receive_json()["event"] == "visit_recorded"


def test_the_counters_route_reads_both_counters(
    client: TestClient, make_token: TokenFactory
) -> None:
    assert client.get(COUNTERS).status_code == 401
    _fake_resources(client)
    client.post(VISIT, headers=_auth(make_token))

    response = client.get(COUNTERS, headers=_auth(make_token))

    assert response.json() == {"databaseVisits": 1, "cacheVisits": 1}


# --- the hub and the shared bus -------------------------------------------------------


class _Sock:
    def __init__(self) -> None:
        self.sent: list[object] = []

    async def send_json(self, data: object) -> None:
        self.sent.append(data)

    async def close(self, code: int = 1000) -> None:
        return None


class _Bus:
    """Stands in for the cache: remembers what was published, may fail."""

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.published: list[dict[str, object]] = []

    async def publish(self, message: dict[str, object]) -> None:
        if self.fail:
            raise ConnectionError("cache down")
        self.published.append(message)


@pytest.mark.anyio
async def test_publish_reaches_local_sockets_and_the_bus() -> None:
    bus = _Bus()
    hub = RealtimeHub(bus=bus)
    sock = _Sock()
    hub.add(sock)

    assert await hub.publish({"event": "x"}) == 1
    assert sock.sent == [{"event": "x"}]
    assert bus.published == [{"event": "x"}]


@pytest.mark.anyio
async def test_a_failing_bus_never_breaks_the_push() -> None:
    hub = RealtimeHub(bus=_Bus(fail=True))
    sock = _Sock()
    hub.add(sock)

    assert await hub.publish({"event": "x"}) == 1
    assert sock.sent == [{"event": "x"}]


def test_a_message_of_another_process_is_decoded_and_the_echo_dropped() -> None:
    raw = encode("proc-a", {"event": "x"})

    assert decode(raw, "proc-b") == {"event": "x"}
    assert decode(raw, "proc-a") is None
    assert decode(raw.encode(), "proc-b") == {"event": "x"}
    assert decode("not json", "proc-b") is None
    assert decode('{"origin": "a", "message": 3}', "proc-b") is None
    assert decode("[1]", "proc-b") is None


def test_the_channel_starts_with_the_cache_key_prefix() -> None:
    assert RedisRealtimeBus("redis://x", "app1:").channel == "app1:realtime"


class _FakePubSub:
    def __init__(self, items: list[dict[str, object]]) -> None:
        self._items = items

    async def __aenter__(self) -> _FakePubSub:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def subscribe(self, channel: str) -> None:
        self.channel = channel

    async def listen(self) -> Any:  # noqa: ANN401
        for item in self._items:
            yield item
        await asyncio.sleep(3600)


class _FakeRedis:
    def __init__(self, items: list[dict[str, object]] | None = None) -> None:
        self.items = items or []
        self.published: list[tuple[str, str]] = []

    def pubsub(self) -> _FakePubSub:
        return _FakePubSub(self.items)

    async def publish(self, channel: str, payload: str) -> None:
        self.published.append((channel, payload))

    async def aclose(self) -> None:
        return None


@pytest.mark.anyio
async def test_the_bus_publishes_with_its_origin_and_delivers_the_others(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bus = RedisRealtimeBus("redis://x", "p:")
    fake = _FakeRedis(
        [
            {"type": "subscribe", "data": 1},
            {"type": "message", "data": encode(bus.origin, {"event": "mine"})},
            {"type": "message", "data": encode("other", {"event": "theirs"})},
        ]
    )
    monkeypatch.setattr(bus, "_client", lambda: fake)
    delivered: list[dict[str, object]] = []

    async def deliver(message: dict[str, object]) -> None:
        delivered.append(message)

    await bus.publish({"event": "out"})
    task = asyncio.create_task(bus.run(deliver))
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert fake.published[0][0] == "p:realtime"
    assert delivered == [{"event": "theirs"}]


@pytest.mark.anyio
async def test_the_listener_retries_when_the_cache_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bus = RedisRealtimeBus("redis://x", "p:")
    attempts: list[int] = []

    class _Broken(_FakeRedis):
        def pubsub(self) -> _FakePubSub:
            attempts.append(1)
            raise ConnectionError("down")

    monkeypatch.setattr(bus, "_client", lambda: _Broken())
    monkeypatch.setattr(realtime_bus, "RECONNECT_MIN_SECONDS", 0.01)

    async def deliver(_message: dict[str, object]) -> None:
        return None

    task = asyncio.create_task(bus.run(deliver))
    await asyncio.sleep(0.2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert len(attempts) >= 2


def test_without_a_cache_there_is_no_bus(config: Config) -> None:
    assert create_app(config).state.realtime_bus is None
