from fastapi.testclient import TestClient

from app.core.config import StorageConfig
from app.services.demo_service import DemoActions
from tests.conftest import USER_UUID, TokenFactory


def _auth(make_token: TokenFactory) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token()}"}


def test_requires_a_token(client: TestClient) -> None:
    assert client.post("/api/v1/demo/visit").status_code == 401


def test_reports_unconfigured_resources(
    client: TestClient, make_token: TokenFactory
) -> None:
    response = client.post("/api/v1/demo/visit", headers=_auth(make_token))

    assert response.status_code == 200
    assert response.json() == {
        "databaseVisits": None,
        "cacheVisits": None,
        "storageObject": None,
    }


def test_writes_and_reads_back_each_resource(
    client: TestClient, make_token: TokenFactory
) -> None:
    seen: list[str] = []

    def database(user: str) -> int:
        seen.append(user)
        return 7

    client.app.state.demo_actions = DemoActions(  # type: ignore[attr-defined]
        database=database, cache=lambda _user: 3, storage=lambda _user: '{"user": "x"}'
    )

    response = client.post("/api/v1/demo/visit", headers=_auth(make_token))

    assert response.json() == {
        "databaseVisits": 7,
        "cacheVisits": 3,
        "storageObject": '{"user": "x"}',
    }
    assert seen == [str(USER_UUID)], (
        "the visitor is the user of the token, never a client-supplied value"
    )


def test_a_failing_resource_is_an_error_not_a_leak(
    client: TestClient, make_token: TokenFactory
) -> None:
    def broken(_user: str) -> int:
        raise ConnectionError("db.internal refused user secret")

    client.app.state.demo_actions = DemoActions(  # type: ignore[attr-defined]
        database=broken, cache=None, storage=None
    )
    quiet = TestClient(client.app, raise_server_exceptions=False)

    response = quiet.post("/api/v1/demo/visit", headers=_auth(make_token))

    assert response.status_code == 500
    assert "secret" not in response.text


def _storage(endpoint: str) -> StorageConfig:
    return StorageConfig.model_validate(
        {"endpoint": endpoint, "access_key": "a", "secret_key": "k", "bucket": "b"}
    )


def test_a_storage_endpoint_without_scheme_gets_one() -> None:
    """A deployed component gets STORAGE_ENDPOINT as host:port, DEV as a URL."""
    assert _storage("bucket-svc:9000").endpoint == "http://bucket-svc:9000"
    assert _storage("http://bucket-svc:9000").endpoint == "http://bucket-svc:9000"
    assert _storage("").endpoint == ""
