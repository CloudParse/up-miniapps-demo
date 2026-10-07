from fastapi.testclient import TestClient


def test_greets_the_world_by_default(client: TestClient) -> None:
    response = client.get("/api/v1/hello")

    assert response.status_code == 200
    assert response.json() == {"message": "Hello, World!"}


def test_greets_a_given_name(client: TestClient) -> None:
    response = client.get("/api/v1/hello", params={"name": "Ada"})

    assert response.json() == {"message": "Hello, Ada!"}


def test_rejects_an_invalid_name(client: TestClient) -> None:
    response = client.get("/api/v1/hello", params={"name": "<script>"})

    assert response.status_code == 422
