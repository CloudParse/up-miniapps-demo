import asyncio
import time

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.api.routes import realtime as realtime_routes
from app.core.config import Config
from app.main import create_app
from app.services.realtime_service import RealtimeHub
from tests.conftest import TokenFactory

BROADCAST = "/api/v1/demo/broadcast"


def _auth(make_token: TokenFactory) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token()}"}


def test_a_pushed_message_reaches_every_open_socket(
    client: TestClient, make_token: TokenFactory
) -> None:
    with (
        client.websocket_connect("/api/v1/ws") as first,
        client.websocket_connect("/api/v1/ws") as second,
    ):
        response = client.post(
            BROADCAST, json={"text": "salut"}, headers=_auth(make_token)
        )

        assert response.status_code == 200
        assert response.json() == {"delivered": 2}
        expected = {"event": "demo_message", "text": "salut"}
        assert first.receive_json() == expected
        assert second.receive_json() == expected


def test_broadcast_without_listener_delivers_to_nobody(
    client: TestClient, make_token: TokenFactory
) -> None:
    response = client.post(BROADCAST, json={"text": "seul"}, headers=_auth(make_token))

    assert response.json() == {"delivered": 0}


def test_rejects_an_empty_or_too_long_message(
    client: TestClient, make_token: TokenFactory
) -> None:
    headers = _auth(make_token)
    assert client.post(BROADCAST, json={"text": ""}, headers=headers).status_code == 422
    too_long = {"text": "x" * 201}
    assert client.post(BROADCAST, json=too_long, headers=headers).status_code == 422


def test_a_socket_that_leaves_is_forgotten(
    client: TestClient, make_token: TokenFactory
) -> None:
    with client.websocket_connect("/api/v1/ws"):
        pass

    assert client.post(
        BROADCAST, json={"text": "x"}, headers=_auth(make_token)
    ).json() == {"delivered": 0}


def test_an_oversized_client_message_closes_the_socket(client: TestClient) -> None:
    with client.websocket_connect("/api/v1/ws") as socket:
        socket.send_text("x" * 2048)
        with pytest.raises(WebSocketDisconnect) as closed:
            socket.receive_text()

    assert closed.value.code == 1009


class _Sock:
    def __init__(self, fail: bool = False, stall: bool = False) -> None:
        self.fail = fail
        self.stall = stall
        self.closed = False
        self.sent: list[object] = []

    async def send_json(self, data: object) -> None:
        if self.fail:
            raise RuntimeError("closed")
        if self.stall:
            await asyncio.sleep(3600)
        self.sent.append(data)

    async def close(self, code: int = 1000) -> None:
        self.closed = True


@pytest.mark.anyio
async def test_the_hub_drops_a_broken_socket_and_keeps_the_others() -> None:
    hub = RealtimeHub()
    good, broken = _Sock(), _Sock(fail=True)
    hub.add(good)
    hub.add(broken)

    assert await hub.broadcast({"a": 1}) == 1
    assert hub.count == 1
    assert good.sent == [{"a": 1}]


def test_the_hub_refuses_a_socket_past_its_limit() -> None:
    hub = RealtimeHub(max_connections=1)

    assert hub.add(_Sock()) is True
    assert hub.add(_Sock()) is False


@pytest.mark.anyio
async def test_a_stalled_socket_does_not_hold_the_broadcast_back() -> None:
    hub = RealtimeHub(send_timeout=0.05)
    good, stalled = _Sock(), _Sock(stall=True)
    hub.add(good)
    hub.add(stalled)

    started = time.monotonic()
    delivered = await hub.broadcast({"a": 1})

    assert delivered == 1
    assert time.monotonic() - started < 1
    assert good.sent == [{"a": 1}]
    assert stalled.closed is True
    assert hub.count == 1


def test_the_hub_refuses_a_client_address_past_its_limit() -> None:
    hub = RealtimeHub(max_per_client=2)

    assert hub.add(_Sock(), "1.1.1.1") is True
    assert hub.add(_Sock(), "1.1.1.1") is True
    assert hub.add(_Sock(), "1.1.1.1") is False
    assert hub.add(_Sock(), "2.2.2.2") is True


def test_a_socket_past_the_hub_limit_is_closed_with_1013(config: Config) -> None:
    app = create_app(config)
    app.state.realtime_hub = RealtimeHub(max_connections=1)
    client = TestClient(app)

    with (
        client.websocket_connect("/api/v1/ws"),
        client.websocket_connect("/api/v1/ws") as refused,
        pytest.raises(WebSocketDisconnect) as closed,
    ):
        refused.receive_text()

    assert closed.value.code == 1013


def test_one_client_address_cannot_fill_the_hub(config: Config) -> None:
    app = create_app(config)
    app.state.realtime_hub = RealtimeHub(max_per_client=1)
    client = TestClient(app)
    # The proxy appends the real peer at the end: what a client puts first is ignored.
    forged = {"X-Forwarded-For": "9.9.9.9, 1.1.1.1"}
    other = {"X-Forwarded-For": "2.2.2.2"}

    with client.websocket_connect("/api/v1/ws", headers=forged):
        with (
            client.websocket_connect("/api/v1/ws", headers=forged) as refused,
            pytest.raises(WebSocketDisconnect) as closed,
        ):
            refused.receive_text()
        with client.websocket_connect("/api/v1/ws", headers=other) as accepted:
            accepted.send_text("ping")

    assert closed.value.code == 1013


def test_a_binary_frame_is_read_and_dropped(client: TestClient) -> None:
    with client.websocket_connect("/api/v1/ws") as socket:
        socket.send_bytes(b"\x00\x01")
        socket.send_text("still here")
        socket.send_bytes(b"\x00" * 2048)
        with pytest.raises(WebSocketDisconnect) as closed:
            socket.receive_text()

    assert closed.value.code == 1009


def test_the_message_cap_counts_bytes_not_characters(client: TestClient) -> None:
    with client.websocket_connect("/api/v1/ws") as socket:
        socket.send_text("é" * 600)  # 600 characters, 1200 bytes
        with pytest.raises(WebSocketDisconnect) as closed:
            socket.receive_text()

    assert closed.value.code == 1009


def test_a_silent_socket_is_closed_after_the_idle_timeout(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(realtime_routes, "IDLE_TIMEOUT_SECONDS", 0.05)

    with (
        client.websocket_connect("/api/v1/ws") as socket,
        pytest.raises(WebSocketDisconnect) as closed,
    ):
        socket.receive_text()

    assert closed.value.code == 1001


@pytest.mark.parametrize("origin", ["null", None, "http://localhost:21515"])
def test_the_sandbox_frame_and_local_pages_may_open_the_socket(
    config: Config, origin: str | None
) -> None:
    client = TestClient(
        create_app(config.model_copy(update={"environment": "development"}))
    )
    headers = {} if origin is None else {"Origin": origin}

    with client.websocket_connect("/api/v1/ws", headers=headers) as socket:
        socket.send_text("ping")


def test_another_website_cannot_open_the_socket(config: Config) -> None:
    client = TestClient(create_app(config))

    with (
        pytest.raises(WebSocketDisconnect),
        client.websocket_connect(
            "/api/v1/ws", headers={"Origin": "https://evil.example"}
        ),
    ):
        pass


def test_a_configured_origin_may_open_the_socket(config: Config) -> None:
    allowed = config.cors.model_copy(
        update={"allowed_origins": ["https://app.example"]}
    )
    client = TestClient(create_app(config.model_copy(update={"cors": allowed})))

    with client.websocket_connect(
        "/api/v1/ws", headers={"Origin": "https://app.example"}
    ) as socket:
        socket.send_text("ping")


def test_the_demo_broadcast_needs_a_signed_in_member(client: TestClient) -> None:
    assert client.post(BROADCAST, json={"text": "x"}).status_code == 401


def test_the_demo_broadcast_does_not_exist_in_production(config: Config) -> None:
    production = TestClient(
        create_app(config.model_copy(update={"environment": "production"}))
    )

    assert production.post(BROADCAST, json={"text": "x"}).status_code == 404
    assert production.get("/docs").status_code == 404
    assert production.get("/openapi.json").status_code == 404
