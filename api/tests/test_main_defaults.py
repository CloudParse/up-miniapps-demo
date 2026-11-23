from pathlib import Path

from app.__main__ import default_to_development
from app.core.config import load_config

CONFIG = Path(__file__).resolve().parent.parent / "configs" / "config.toml"


def test_the_shipped_config_runs_as_production_when_nothing_says_otherwise() -> None:
    assert load_config(CONFIG, environ={}).environment == "production"


def test_an_env_file_means_development_unless_the_environment_says_otherwise(
    tmp_path: Path,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("DATABASE_URL=x\n")

    unset: dict[str, str] = {}
    assert default_to_development(env_file, unset) is True
    assert unset == {"ENVIRONMENT": "development"}

    pinned = {"ENVIRONMENT": "production"}
    assert default_to_development(env_file, pinned) is False
    assert pinned == {"ENVIRONMENT": "production"}


def test_without_an_env_file_nothing_is_set(tmp_path: Path) -> None:
    environ: dict[str, str] = {}

    assert default_to_development(tmp_path / ".env", environ) is False
    assert environ == {}
