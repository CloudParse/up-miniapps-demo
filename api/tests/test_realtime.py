import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.services.realtime_service import RealtimeHub


def test_a_pushed_message_reaches_every_open_socket(client: TestClient) -> None:
    with (
        client.websocket_connect("/api/v1/ws") as first,
        client.websocket_connect("/api/v1/ws") as second,
    ):
        response = client.post("/api/v1/demo/broadcast", json={"text": "salut"})

        assert response.status_code == 200
        assert response.json() == {"delivered": 2}
        expected = {"event": "demo_message", "text": "salut"}
        assert first.receive_json() == expected
        assert second.receive_json() == expected


def test_broadcast_without_listener_delivers_to_nobody(client: TestClient) -> None:
    response = client.post("/api/v1/demo/broadcast", json={"text": "seul"})

    assert response.json() == {"delivered": 0}


def test_rejects_an_empty_or_too_long_message(client: TestClient) -> None:
    assert client.post("/api/v1/demo/broadcast", json={"text": ""}).status_code == 422
    assert (
        client.post("/api/v1/demo/broadcast", json={"text": "x" * 201}).status_code
        == 422
    )


def test_a_socket_that_leaves_is_forgotten(client: TestClient) -> None:
    with client.websocket_connect("/api/v1/ws"):
        pass

    assert client.post("/api/v1/demo/broadcast", json={"text": "x"}).json() == {
        "delivered": 0
    }


def test_an_oversized_client_message_closes_the_socket(client: TestClient) -> None:
    with client.websocket_connect("/api/v1/ws") as socket:
        socket.send_text("x" * 2048)
        with pytest.raises(WebSocketDisconnect) as closed:
            socket.receive_text()

    assert closed.value.code == 1009


class _Sock:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.sent: list[object] = []

    async def send_json(self, data: object) -> None:
        if self.fail:
            raise RuntimeError("closed")
        self.sent.append(data)


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
