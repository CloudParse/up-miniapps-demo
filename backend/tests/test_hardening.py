from fastapi.testclient import TestClient

from app.core.config import Config
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
