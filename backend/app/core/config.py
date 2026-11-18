"""Typed configuration loaded from a TOML file, overridable by environment.

Mirrors the Go backends of the Up family: the TOML file holds safe defaults,
and the dotted key upper-cased with underscores overrides it
(``hub.base_url`` -> ``HUB_BASE_URL``). Only keys present in the TOML file can
be overridden, so the file doubles as the list of every supported setting.
"""

import os
import tomllib
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, SecretStr

DEFAULT_CONFIG_PATH = "configs/config.toml"
CONFIG_PATH_ENV_VAR = "CONFIG_PATH"


class _Section(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ServerConfig(_Section):
    host: str
    port: int


class HubConfig(_Section):
    base_url: str
    public_key_path: Path
    app_uuid: str
    client_secret: SecretStr


class CorsConfig(_Section):
    allowed_origins: list[str]


class Config(_Section):
    # Top-level on purpose: it must bind to a plain ENVIRONMENT variable.
    environment: Literal["development", "test", "production"]
    server: ServerConfig
    hub: HubConfig
    cors: CorsConfig

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


def load_config(path: Path, environ: Mapping[str, str] | None = None) -> Config:
    """Read ``path`` and apply environment overrides (``os.environ`` by default)."""
    if not path.is_file():
        raise FileNotFoundError(f"Config file not found: {path}")
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    overridden = _apply_env_overrides(raw, os.environ if environ is None else environ)
    return Config.model_validate(overridden)


@lru_cache
def get_config() -> Config:
    """Process-wide configuration, read once from ``CONFIG_PATH``."""
    return load_config(Path(os.environ.get(CONFIG_PATH_ENV_VAR, DEFAULT_CONFIG_PATH)))


def _apply_env_overrides(
    section: Mapping[str, Any],
    environ: Mapping[str, str],
    prefix: tuple[str, ...] = (),
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, default in section.items():
        key_path = (*prefix, key)
        if isinstance(default, dict):
            result[key] = _apply_env_overrides(default, environ, key_path)
            continue
        env_value = environ.get("_".join(key_path).upper())
        result[key] = default if env_value is None else _coerce(env_value, default)
    return result


def _coerce(env_value: str, default: object) -> object:
    # Lists are comma-separated in the environment; pydantic coerces the
    # remaining scalars ("21514" -> int, "true" -> bool).
    if isinstance(default, list):
        return [item.strip() for item in env_value.split(",") if item.strip()]
    return env_value
