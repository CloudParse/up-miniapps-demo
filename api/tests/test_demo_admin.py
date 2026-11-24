from datetime import UTC, datetime
from typing import Any

import psycopg
import pytest
import redis
from fastapi.testclient import TestClient

from app.core.config import Config, StorageConfig
from app.main import create_app
from app.schemas.demo_admin import DemoNote
from app.services import demo_admin_service
from app.services.demo_admin_service import DemoAdminActions
from tests.conftest import TokenFactory

OVERVIEW = "/api/v1/admin/demo/overview"
RESET = "/api/v1/admin/demo/reset-cache"


def _bearer(make_token: TokenFactory, *, admin: bool) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(admin=admin)}"}


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


def test_the_objects_are_counted_under_the_demo_prefix_with_a_cap(
    config: Config, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked: list[dict[str, Any]] = []

    class Stub:
        def list_objects_v2(self, **kwargs: Any) -> dict[str, int]:
            asked.append(kwargs)
            return {"KeyCount": 3}

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
    assert asked == [{"Bucket": "b", "Prefix": "demo/", "MaxKeys": 1000}]


def test_one_failing_resource_does_not_fail_the_overview(
    client: TestClient, make_token: TokenFactory
) -> None:
    def broken() -> int:
        raise ConnectionError("db.internal refused user secret")

    client.app.state.demo_admin_actions = DemoAdminActions(  # type: ignore[attr-defined]
        database_visits=broken,
        cache_visits=lambda: 3,
        storage_objects=lambda: 2,
        reset_cache_visits=None,
    )

    response = client.get(OVERVIEW, headers=_bearer(make_token, admin=True))

    assert response.status_code == 200
    assert response.json() == {
        "databaseVisits": None,
        "cacheVisits": 3,
        "storageObjects": 2,
    }
    assert "secret" not in response.text


NOTES = "/api/v1/admin/demo/notes"


def test_the_note_routes_need_a_token_and_the_admin_scope(
    client: TestClient, make_token: TokenFactory
) -> None:
    assert client.get(NOTES).status_code == 401
    assert client.post(NOTES, json={"text": "Hi"}).status_code == 401
    user = _bearer(make_token, admin=False)
    assert client.get(NOTES, headers=user).status_code == 403
    assert client.post(NOTES, json={"text": "Hi"}, headers=user).status_code == 403


def test_the_note_routes_answer_503_without_a_database(
    client: TestClient, make_token: TokenFactory
) -> None:
    admin = _bearer(make_token, admin=True)

    response = client.post(NOTES, json={"text": "Hi"}, headers=admin)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"
    assert client.get(NOTES, headers=admin).status_code == 503


def test_an_admin_writes_a_note_and_reads_it_back(
    client: TestClient, make_token: TokenFactory
) -> None:
    saved: list[DemoNote] = []

    def add(text: str) -> DemoNote:
        note = DemoNote(id=len(saved) + 1, text=text, created_at=datetime.now(UTC))
        saved.append(note)
        return note

    client.app.state.demo_admin_actions = DemoAdminActions(  # type: ignore[attr-defined]
        database_visits=None,
        cache_visits=None,
        storage_objects=None,
        reset_cache_visits=None,
        list_notes=lambda: list(reversed(saved)),
        add_note=add,
    )
    admin = _bearer(make_token, admin=True)

    created = client.post(NOTES, json={"text": "  Open at 8 pm  "}, headers=admin)
    listed = client.get(NOTES, headers=admin)

    assert created.status_code == 201
    assert created.json()["text"] == "Open at 8 pm"
    assert "createdAt" in created.json()
    assert [note["text"] for note in listed.json()] == ["Open at 8 pm"]


@pytest.mark.parametrize("text", ["", "   ", "x" * 201])
def test_a_note_must_hold_1_to_200_characters(
    client: TestClient, make_token: TokenFactory, text: str
) -> None:
    response = client.post(
        NOTES, json={"text": text}, headers=_bearer(make_token, admin=True)
    )

    assert response.status_code == 422


def test_the_note_routes_are_not_served_in_production(
    config: Config, make_token: TokenFactory
) -> None:
    production = TestClient(
        create_app(config.model_copy(update={"environment": "production"}))
    )
    headers = _bearer(make_token, admin=True)

    assert production.get(NOTES, headers=headers).status_code == 404
    assert (
        production.post(NOTES, json={"text": "Hi"}, headers=headers).status_code == 404
    )


def test_the_note_routes_answer_503_when_the_database_does_not_answer(
    client: TestClient, make_token: TokenFactory
) -> None:
    def down() -> list[DemoNote]:
        raise psycopg.OperationalError("db.internal refused user secret")

    client.app.state.demo_admin_actions = DemoAdminActions(  # type: ignore[attr-defined]
        database_visits=None,
        cache_visits=None,
        storage_objects=None,
        reset_cache_visits=None,
        list_notes=down,
    )

    response = client.get(NOTES, headers=_bearer(make_token, admin=True))

    assert response.status_code == 503
    assert "secret" not in response.text
