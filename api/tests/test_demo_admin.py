from typing import Any

import pytest
import redis
from fastapi.testclient import TestClient

from app.core.config import Config, StorageConfig
from app.core.security import ADMIN_SCOPE
from app.main import create_app
from app.services import demo_admin_service
from app.services.demo_admin_service import DemoAdminActions
from tests.conftest import TokenFactory

OVERVIEW = "/api/v1/admin/demo/overview"
RESET = "/api/v1/admin/demo/reset-cache"


def _bearer(make_token: TokenFactory, *, admin: bool) -> dict[str, str]:
    scopes = ("profile:username", ADMIN_SCOPE) if admin else ("profile:username",)
    return {"Authorization": f"Bearer {make_token(scopes=scopes)}"}


def test_the_plugin_routes_need_a_token_and_the_admin_scope(
    client: TestClient, make_token: TokenFactory
) -> None:
    assert client.get(OVERVIEW).status_code == 401
    assert client.post(RESET).status_code == 401
    assert (
        client.get(OVERVIEW, headers=_bearer(make_token, admin=False)).status_code
        == 403
    )
    assert (
        client.post(RESET, headers=_bearer(make_token, admin=False)).status_code == 403
    )


def test_the_overview_reports_unconfigured_resources(
    client: TestClient, make_token: TokenFactory
) -> None:
    response = client.get(OVERVIEW, headers=_bearer(make_token, admin=True))

    assert response.status_code == 200
    assert response.json() == {
        "databaseVisits": None,
        "cacheVisits": None,
        "storageObjects": None,
    }


def test_the_overview_reads_each_resource_through_the_api(
    client: TestClient, make_token: TokenFactory
) -> None:
    client.app.state.demo_admin_actions = DemoAdminActions(  # type: ignore[attr-defined]
        database_visits=lambda: 7,
        cache_visits=lambda: 3,
        storage_objects=lambda: 2,
        reset_cache_visits=None,
    )

    response = client.get(OVERVIEW, headers=_bearer(make_token, admin=True))

    assert response.json() == {
        "databaseVisits": 7,
        "cacheVisits": 3,
        "storageObjects": 2,
    }


def test_the_reset_clears_the_counter_and_returns_the_new_overview(
    client: TestClient, make_token: TokenFactory
) -> None:
    counter = {"value": 5}

    def reset() -> None:
        counter["value"] = 0

    client.app.state.demo_admin_actions = DemoAdminActions(  # type: ignore[attr-defined]
        database_visits=None,
        cache_visits=lambda: counter["value"],
        storage_objects=None,
        reset_cache_visits=reset,
    )

    response = client.post(RESET, headers=_bearer(make_token, admin=True))

    assert response.status_code == 200
    assert response.json()["cacheVisits"] == 0


def test_the_plugin_routes_are_not_served_in_production(
    config: Config, make_token: TokenFactory
) -> None:
    production = TestClient(
        create_app(config.model_copy(update={"environment": "production"}))
    )
    headers = _bearer(make_token, admin=True)

    assert production.get(OVERVIEW, headers=headers).status_code == 404
    assert production.post(RESET, headers=headers).status_code == 404


def test_the_cache_is_read_and_reset_under_the_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    keys: list[tuple[str, str]] = []

    class Stub:
        def get(self, key: str) -> bytes | None:
            keys.append(("get", key))
            return b"4"

        def delete(self, key: str) -> None:
            keys.append(("delete", key))

        def close(self) -> None:
            return None

    monkeypatch.setattr(redis.Redis, "from_url", lambda *_a, **_k: Stub())

    assert demo_admin_service._read_cache_visits("redis://x", "dev_ab12:") == 4
    demo_admin_service._reset_cache_visits("redis://x", "dev_ab12:")

    assert keys == [("get", "dev_ab12:demo:visits"), ("delete", "dev_ab12:demo:visits")]


def test_the_objects_are_counted_under_the_demo_prefix(
    config: Config, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked: list[dict[str, Any]] = []

    class Paginator:
        def paginate(self, **kwargs: Any) -> list[dict[str, int]]:
            asked.append(kwargs)
            return [{"KeyCount": 2}, {"KeyCount": 1}]

    class Stub:
        def get_paginator(self, name: str) -> Paginator:
            assert name == "list_objects_v2"
            return Paginator()

    monkeypatch.setattr(demo_admin_service, "storage_client", lambda _c: Stub())
    storage = StorageConfig.model_validate(
        {
            "endpoint": "http://bucket-svc:9000",
            "access_key": "a",
            "secret_key": "k",
            "bucket": "b",
        }
    )

    count = demo_admin_service._count_objects(
        config.model_copy(update={"storage": storage})
    )

    assert count == 3
    assert asked == [{"Bucket": "b", "Prefix": "demo/"}]
