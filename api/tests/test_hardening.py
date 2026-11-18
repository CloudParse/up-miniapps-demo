from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Config
from app.core.security import build_token_verifier
from app.main import create_app
from tests.conftest import TokenFactory

DEV_SHELL_AUDIENCE = "99999999-9999-9999-9999-999999999999"
LOCAL_ORIGIN = "http://localhost:21515"


def _client(config: Config, environment: str, **cors: object) -> TestClient:
    updated = config.model_copy(
        update={
            "environment": environment,
            "cors": config.cors.model_copy(update=cors),
        }
    )
    return TestClient(create_app(updated))


def test_docs_are_served_outside_production(config: Config) -> None:
    assert _client(config, "development").get("/docs").status_code == 200


def test_docs_and_openapi_are_hidden_in_production(config: Config) -> None:
    client = _client(config, "production")

    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_dev_shell_audience_is_accepted_only_in_development(
    config: Config, make_token: TokenFactory
) -> None:
    headers = {"Authorization": f"Bearer {make_token(audience=DEV_SHELL_AUDIENCE)}"}

    assert (
        _client(config, "development").get("/api/v1/me", headers=headers).status_code
        == 200
    )
    assert (
        _client(config, "production").get("/api/v1/me", headers=headers).status_code
        == 401
    )


def test_local_origins_are_allowed_only_in_development(config: Config) -> None:
    headers = {"Origin": LOCAL_ORIGIN}

    development = _client(config, "development").get("/healthz", headers=headers)
    production = _client(config, "production").get("/healthz", headers=headers)

    assert development.headers.get("access-control-allow-origin") == LOCAL_ORIGIN
    assert "access-control-allow-origin" not in production.headers


def test_configured_origins_are_allowed(config: Config) -> None:
    origin = "https://app.cloudparse.fr"
    client = _client(config, "production", allowed_origins=[origin])

    response = client.get("/healthz", headers={"Origin": origin})

    assert response.headers["access-control-allow-origin"] == origin


def test_a_missing_hub_key_disables_authentication_in_development_only(
    config: Config, tmp_path: Path
) -> None:
    missing = config.hub.model_copy(update={"public_key_path": tmp_path / "none.pem"})

    development = config.model_copy(
        update={"environment": "development", "hub": missing}
    )
    assert build_token_verifier(development) is None

    production = config.model_copy(update={"environment": "production", "hub": missing})
    with pytest.raises(FileNotFoundError):
        build_token_verifier(production)


def test_production_refuses_the_dev_mock_registration(config: Config) -> None:
    mock = config.hub.model_copy(
        update={"app_uuid": "0d0d0d0d-0000-4000-8000-000000000001"}
    )
    production = config.model_copy(update={"environment": "production", "hub": mock})

    with pytest.raises(ValueError, match="DEV mock registration"):
        build_token_verifier(production)
