from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import load_config

TOML = """
environment = "development"

[server]
host = "127.0.0.1"
port = 21514

[hub]
base_url = "http://hub.invalid"
public_key_path = "key.pem"
app_uuid = ""
client_secret = ""

[database]
url = ""

[cache]
url = ""
key_prefix = ""

[storage]
endpoint = ""
access_key = ""
secret_key = ""
bucket = ""

[cors]
allowed_origins = []
"""


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    path = tmp_path / "config.toml"
    path.write_text(TOML)
    return path


def test_reads_values_from_the_file(config_file: Path) -> None:
    config = load_config(config_file, environ={})

    assert config.environment == "development"
    assert config.server.port == 21514
    assert config.hub.app_uuid == ""


def test_top_level_environment_binds_to_plain_environment_variable(
    config_file: Path,
) -> None:
    config = load_config(config_file, environ={"ENVIRONMENT": "production"})

    assert config.environment == "production"
    assert config.is_production


def test_unknown_environment_name_is_rejected(config_file: Path) -> None:
    # A typo such as "prod" must fail at startup, not silently disable hardening.
    with pytest.raises(ValidationError):
        load_config(config_file, environ={"ENVIRONMENT": "prod"})


def test_nested_keys_bind_to_upper_snake_case_variables(config_file: Path) -> None:
    config = load_config(
        config_file,
        environ={"SERVER_PORT": "9000", "HUB_CLIENT_SECRET": "s3cr3t"},
    )

    assert config.server.port == 9000
    assert config.hub.client_secret.get_secret_value() == "s3cr3t"


def test_list_values_are_comma_separated(config_file: Path) -> None:
    config = load_config(
        config_file,
        environ={
            "CORS_ALLOWED_ORIGINS": "https://a.cloudparse.fr, https://b.cloudparse.fr"
        },
    )

    assert config.cors.allowed_origins == [
        "https://a.cloudparse.fr",
        "https://b.cloudparse.fr",
    ]


def test_secrets_are_masked_when_printed(config_file: Path) -> None:
    config = load_config(config_file, environ={"HUB_CLIENT_SECRET": "s3cr3t"})

    assert "s3cr3t" not in repr(config)


def test_missing_file_fails_loudly(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "missing.toml", environ={})


def test_resources_bind_to_the_names_a_deployed_component_gets(
    config_file: Path,
) -> None:
    config = load_config(
        config_file,
        environ={
            "DATABASE_URL": "postgresql://u:pw@db/app",
            "CACHE_URL": "redis://u:pw@cache:6379",
            "CACHE_KEY_PREFIX": "demo:",
            "STORAGE_ENDPOINT": "http://bucket:9000",
            "STORAGE_SECRET_KEY": "s3-secret",
            "STORAGE_BUCKET": "demo",
        },
    )

    assert config.database.url.get_secret_value() == "postgresql://u:pw@db/app"
    assert config.cache.key_prefix == "demo:"
    assert config.storage.bucket == "demo"
    assert "pw" not in repr(config) and "s3-secret" not in repr(config)


def test_the_checked_in_file_loads() -> None:
    config = load_config(Path("configs/config.toml"), environ={})

    assert config.hub.app_uuid == "0d0d0d0d-0000-4000-8000-000000000001"
