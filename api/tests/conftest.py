import time
from collections.abc import Callable
from pathlib import Path
from uuid import UUID, uuid4

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from app.core.config import Config
from app.main import create_app

APP_UUID = "00000000-0000-0000-0000-0000000000a1"
USER_UUID = UUID("00000000-0000-0000-0000-0000000000b2")

TokenFactory = Callable[..., str]


def _pem(key: ec.EllipticCurvePrivateKey) -> str:
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()


@pytest.fixture(scope="session")
def hub_private_key() -> ec.EllipticCurvePrivateKey:
    """Stands in for the Hub's signing key; the app only ever sees the public half."""
    return ec.generate_private_key(ec.SECP256R1())


@pytest.fixture
def config(tmp_path: Path, hub_private_key: ec.EllipticCurvePrivateKey) -> Config:
    public_key_path = tmp_path / "public.pem"
    public_key_path.write_bytes(
        hub_private_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    return Config.model_validate(
        {
            "environment": "test",
            "server": {"host": "127.0.0.1", "port": 0},
            "hub": {
                "base_url": "http://hub.invalid/api/v1",
                "public_key_path": str(public_key_path),
                "app_uuid": APP_UUID,
                "client_secret": "test-secret",
            },
            "database": {"url": ""},
            "cache": {"url": "", "key_prefix": ""},
            "storage": {
                "endpoint": "",
                "access_key": "",
                "secret_key": "",
                "bucket": "",
            },
            "cors": {"allowed_origins": []},
        }
    )


@pytest.fixture
def client(config: Config) -> TestClient:
    return TestClient(create_app(config))


@pytest.fixture
def make_token(hub_private_key: ec.EllipticCurvePrivateKey) -> TokenFactory:
    def _make_token(
        *,
        audience: str = APP_UUID,
        expires_in: int = 300,
        key: ec.EllipticCurvePrivateKey | None = None,
        scopes: tuple[str, ...] = ("profile:username",),
    ) -> str:
        return jwt.encode(
            {
                "sub": str(USER_UUID),
                "aud": audience,
                "exp": int(time.time()) + expires_in,
                "scp": list(scopes),
                "jti": str(uuid4()),
            },
            _pem(key or hub_private_key),
            algorithm="ES256",
        )

    return _make_token
