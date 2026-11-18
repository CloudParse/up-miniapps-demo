from fastapi.testclient import TestClient

from app.services.resource_service import ResourceProbes
from tests.conftest import TokenFactory


def _fail() -> None:
    raise ConnectionError("db.internal refused user secret")


def test_requires_a_token(client: TestClient) -> None:
    response = client.get("/api/v1/resources")

    assert response.status_code == 401


def test_reports_unconfigured_resources(
    client: TestClient, make_token: TokenFactory
) -> None:
    response = client.get(
        "/api/v1/resources", headers={"Authorization": f"Bearer {make_token()}"}
    )

    assert response.status_code == 200
    assert response.json() == {
        "database": "not_configured",
        "cache": "not_configured",
        "storage": "not_configured",
    }


def test_reports_each_probe_without_its_cause(
    client: TestClient, make_token: TokenFactory
) -> None:
    client.app.state.resource_probes = ResourceProbes(  # type: ignore[attr-defined]
        database=lambda: None, cache=_fail, storage=None
    )

    response = client.get(
        "/api/v1/resources", headers={"Authorization": f"Bearer {make_token()}"}
    )

    assert response.json() == {
        "database": "ok",
        "cache": "unreachable",
        "storage": "not_configured",
    }
    assert "secret" not in response.text
