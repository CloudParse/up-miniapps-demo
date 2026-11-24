import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from tests.conftest import TokenFactory

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
