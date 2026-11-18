import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from app.core.config import Config
from app.main import create_app
from tests.conftest import APP_UUID, USER_UUID, TokenFactory

ME = "/api/v1/me"


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_returns_the_identity_of_a_valid_token(
    client: TestClient, make_token: TokenFactory
) -> None:
    response = client.get(ME, headers=_bearer(make_token()))

    assert response.status_code == 200
    assert response.json() == {
        "userUuid": str(USER_UUID),
        "scopes": ["profile:username"],
    }


def test_rejects_a_missing_token(client: TestClient) -> None:
    response = client.get(ME)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


@pytest.mark.parametrize(
    "token_kwargs",
    [
        {"expires_in": -60},
        {"audience": "00000000-0000-0000-0000-00000000ffff"},
        {"key": ec.generate_private_key(ec.SECP256R1())},
    ],
    ids=["expired", "other-app-audience", "foreign-signature"],
)
def test_rejects_an_untrustworthy_token(
    client: TestClient, make_token: TokenFactory, token_kwargs: dict[str, object]
) -> None:
    response = client.get(ME, headers=_bearer(make_token(**token_kwargs)))

    assert response.status_code == 401


def test_rejects_garbage(client: TestClient) -> None:
    response = client.get(ME, headers=_bearer("not-a-jwt"))

    assert response.status_code == 401


def test_reports_unavailable_until_the_app_is_registered(config: Config) -> None:
    unregistered = config.model_copy(
        update={"hub": config.hub.model_copy(update={"app_uuid": ""})}
    )

    response = TestClient(create_app(unregistered)).get(ME)

    assert response.status_code == 503


def test_rejects_a_scope_claim_that_is_not_a_list(
    client: TestClient, hub_private_key: ec.EllipticCurvePrivateKey
) -> None:
    token = jwt.encode(
        {
            "sub": str(USER_UUID),
            "aud": APP_UUID,
            "exp": int(time.time()) + 300,
            "scp": "abc",
        },
        hub_private_key,
        algorithm="ES256",
    )

    assert client.get(ME, headers=_bearer(token)).status_code == 401
