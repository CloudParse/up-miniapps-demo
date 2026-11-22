import os
from pathlib import Path
from typing import Any

import pytest
import uvicorn

from app import __main__ as entry
from app.core import config as config_module
from app.core.config import load_config
from app.core.dotenv import load_dotenv

API_DIR = Path(__file__).resolve().parent.parent


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / ".env"
    path.write_text(text, encoding="utf-8")
    return path


def test_reads_plain_values_and_ignores_comments_and_blank_lines(
    tmp_path: Path,
) -> None:
    environ: dict[str, str] = {}
    path = _write(
        tmp_path,
        "# a comment\n\nDATABASE_URL=postgres://u:p@db/x\nCACHE_KEY_PREFIX=dev_ab:  \n",
    )

    loaded = load_dotenv(path, environ)

    assert environ == {
        "DATABASE_URL": "postgres://u:p@db/x",
        "CACHE_KEY_PREFIX": "dev_ab:",
    }
    assert loaded == ["DATABASE_URL", "CACHE_KEY_PREFIX"]


def test_a_variable_already_in_the_environment_is_never_overridden(
    tmp_path: Path,
) -> None:
    environ = {"HUB_APP_UUID": "from-the-shell", "EMPTY": ""}
    path = _write(tmp_path, "HUB_APP_UUID=from-the-file\nEMPTY=x\nNEW=1\n")

    loaded = load_dotenv(path, environ)

    assert environ == {"HUB_APP_UUID": "from-the-shell", "EMPTY": "", "NEW": "1"}
    assert loaded == ["NEW"]


def test_quotes(tmp_path: Path) -> None:
    environ: dict[str, str] = {}
    path = _write(
        tmp_path,
        'A="two words" # tail\n'
        "B='it is # literal \\n'\n"
        'C="line\\nbreak \\"quoted\\" back\\\\slash"\n'
        'D=""\n'
        "E='unterminated\n",
    )

    load_dotenv(path, environ)

    assert environ["A"] == "two words"
    assert environ["B"] == "it is # literal \\n"
    assert environ["C"] == 'line\nbreak "quoted" back\\slash'
    assert environ["D"] == ""
    assert environ["E"] == "unterminated"


def test_a_hash_starts_a_comment_only_after_a_space(tmp_path: Path) -> None:
    environ: dict[str, str] = {}
    path = _write(tmp_path, "URL=redis://h/0#frag # a comment\nPLAIN=v #c\n")

    load_dotenv(path, environ)

    assert environ == {"URL": "redis://h/0#frag", "PLAIN": "v"}


def test_export_prefix_and_invalid_lines(tmp_path: Path) -> None:
    environ: dict[str, str] = {}
    path = _write(
        tmp_path,
        "export TOKEN_PATH=/etc/key.pem\nnot a pair\n1BAD=x\nBAD KEY=y\n=z\n"
        "OK = spaced\n",
    )

    load_dotenv(path, environ)

    assert environ == {"TOKEN_PATH": "/etc/key.pem", "OK": "spaced"}


def test_an_absent_file_is_a_no_op(tmp_path: Path) -> None:
    environ = {"KEEP": "1"}

    assert load_dotenv(tmp_path / "missing.env", environ) == []
    assert environ == {"KEEP": "1"}


def test_the_dev_entry_looks_for_env_in_the_api_folder_not_the_working_directory() -> (
    None
):
    assert entry.ENV_FILE == API_DIR / ".env"


def test_main_reads_the_env_file_before_it_builds_the_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The reported bug: only `uv run --env-file .env` read api/.env."""
    for name in ("SERVER_PORT", "SERVER_HOST", "ENVIRONMENT", "CONFIG_PATH"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)  # not the api folder
    monkeypatch.setenv("CONFIG_PATH", str(API_DIR / "configs" / "config.toml"))
    monkeypatch.setenv("SERVER_HOST", "127.0.0.1")  # the shell wins over the file
    env_file = _write(tmp_path, "SERVER_PORT=24680\nSERVER_HOST=0.0.0.0\n")
    monkeypatch.setattr(entry, "ENV_FILE", env_file)
    config_module.get_config.cache_clear()
    started: list[dict[str, Any]] = []
    monkeypatch.setattr(uvicorn, "run", lambda *_a, **kw: started.append(kw))

    try:
        entry.main()
    finally:
        config_module.get_config.cache_clear()
        for name in ("SERVER_PORT", "SERVER_HOST"):
            os.environ.pop(name, None)

    assert started[0]["port"] == 24680
    assert started[0]["host"] == "127.0.0.1"


def test_the_shipped_defaults_listen_on_every_interface_for_coder() -> None:
    config = load_config(API_DIR / "configs" / "config.toml", environ={})

    assert config.server.host == "0.0.0.0"  # noqa: S104 - dev default, see config.toml
    assert config.server.port == 21514
