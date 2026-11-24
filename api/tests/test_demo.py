from typing import Any

import pytest
from fastapi.testclient import TestClient
from psycopg import errors as pg_errors

from app.core.config import Config, StorageConfig
from app.main import create_app
from app.services import demo_service
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


def test_the_demo_is_not_served_in_production(config: Config) -> None:
    production = TestClient(
        create_app(config.model_copy(update={"environment": "production"}))
    )

    assert production.get("/api/v1/demo").status_code == 404
    assert production.post("/api/v1/demo/visit").status_code == 404


def test_the_demo_announces_itself_outside_production(client: TestClient) -> None:
    response = client.get("/api/v1/demo")

    assert response.status_code == 200
    assert response.json() == {"enabled": True}


def test_a_storage_endpoint_scheme_is_http_or_https() -> None:
    with pytest.raises(ValueError, match="http"):
        _storage("ftp://bucket-svc:9000")


def test_the_cache_key_starts_with_the_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    keys: list[str] = []

    class Stub:
        def incr(self, key: str) -> int:
            keys.append(key)
            return 1

        def close(self) -> None:
            return None

    monkeypatch.setattr(
        "app.services.demo_service.redis.Redis.from_url", lambda *_a, **_k: Stub()
    )

    demo_service._record_cache("redis://x", "dev_ab12:", "user")

    assert keys == ["dev_ab12:demo:visits"]


def test_the_object_key_is_the_visitors_own(
    config: Config, monkeypatch: pytest.MonkeyPatch
) -> None:
    puts: list[str] = []

    class Stub:
        def put_object(self, **kwargs: Any) -> None:
            puts.append(kwargs["Key"])

        def get_object(self, **kwargs: Any) -> dict[str, Any]:
            class Body:
                def read(self) -> bytes:
                    return b"{}"

            assert kwargs["Key"] == puts[-1]
            return {"Body": Body()}

    monkeypatch.setattr(
        "app.services.demo_service.boto3.client", lambda *_a, **_k: Stub()
    )
    storage = _storage("http://bucket-svc:9000")
    cfg = config.model_copy(update={"storage": storage})

    demo_service._record_storage(cfg, "11111111-1111-1111-1111-111111111111")

    assert puts == ["demo/11111111-1111-1111-1111-111111111111.json"]


def test_the_table_is_created_once_at_startup_with_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(demo_service, "SCHEMA_PAUSE_SECONDS", 0)
    monkeypatch.setattr("app.services.demo_service.time.sleep", lambda _s: None)
    calls: list[int] = []

    def flaky() -> None:
        calls.append(1)
        if len(calls) < 3:
            raise ConnectionError("database not ready")

    demo_service.prepare(DemoActions(None, None, None, prepare=flaky))

    assert len(calls) == 3, "retried until the database answers, then stopped"


def test_a_concurrent_table_creation_is_not_an_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Connection:
        def __enter__(self) -> Connection:
            return self

        def __exit__(self, *_a: object) -> None:
            return None

        def execute(self, *_a: object) -> None:
            raise pg_errors.UniqueViolation("pg_type_typname_nsp_index")

    monkeypatch.setattr(
        "app.services.demo_service.psycopg.connect", lambda *_a, **_k: Connection()
    )

    demo_service.ensure_schema("postgres://x")  # must not raise


def test_a_missing_privilege_is_one_clear_line_and_not_retried(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(demo_service, "SCHEMA_PAUSE_SECONDS", 0)
    calls: list[int] = []

    def refused() -> None:
        calls.append(1)
        raise pg_errors.InsufficientPrivilege("permission denied for schema public")

    with caplog.at_level("ERROR"):
        demo_service.prepare(DemoActions(None, None, None, prepare=refused))

    assert len(calls) == 1
    assert "~/.config/up/env" in caplog.text
    assert "Traceback" not in caplog.text
