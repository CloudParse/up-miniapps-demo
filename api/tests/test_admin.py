from fastapi.testclient import TestClient

from app.core.security import ADMIN_SCOPE
from tests.conftest import TokenFactory

ADMIN_HELLO = "/api/v1/admin/hello"


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_admin_scope_unlocks_admin_routes(
    client: TestClient, make_token: TokenFactory
) -> None:
    token = make_token(scopes=("profile:username", ADMIN_SCOPE))

    response = client.get(ADMIN_HELLO, headers=_bearer(token))

    assert response.status_code == 200
    assert response.json() == {"message": "Hello, administrator!"}


def test_regular_user_is_forbidden(
    client: TestClient, make_token: TokenFactory
) -> None:
    response = client.get(ADMIN_HELLO, headers=_bearer(make_token()))

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_anonymous_caller_is_unauthorized(client: TestClient) -> None:
    assert client.get(ADMIN_HELLO).status_code == 401


def test_regular_user_can_still_use_non_admin_routes(
    client: TestClient, make_token: TokenFactory
) -> None:
    assert client.get("/api/v1/me", headers=_bearer(make_token())).status_code == 200
