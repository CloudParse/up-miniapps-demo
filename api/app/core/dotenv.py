"""Minimal ``.env`` loader for the development entry point (standard library only).

``uv run --env-file .env python -m app`` loads the file before Python starts. A plain
``python -m app`` does not, and the API then silently falls back to the defaults of
``configs/config.toml``. This loader makes both commands give the same result.

It reads ``KEY=VALUE`` lines. It never overrides a variable that is already in the
environment, so a real shell variable (or the production container) always wins.
Values are never logged.
"""

import os
import re
from collections.abc import MutableMapping
from pathlib import Path

_KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_ESCAPES = {"n": "\n", "r": "\r", "t": "\t", '"': '"', "\\": "\\"}


def load_dotenv(
    path: Path, environ: MutableMapping[str, str] | None = None
) -> list[str]:
    """Set the variables of ``path`` that ``environ`` does not have yet.

    Returns the names it set. A missing file is not an error: it returns ``[]``,
    which keeps the production image (no ``.env``) unchanged.
    """
    target = os.environ if environ is None else environ
    if not path.is_file():
        return []
    loaded: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        parsed = _parse_line(line)
        if parsed is None:
            continue
        name, value = parsed
        if name in target:
            continue
        target[name] = value
        loaded.append(name)
    return loaded


def _parse_line(line: str) -> tuple[str, str] | None:
    text = line.strip()
    if not text or text.startswith("#"):
        return None
    if text.startswith("export "):
        text = text.removeprefix("export ").lstrip()
    name, separator, raw = text.partition("=")
    name = name.strip()
    if not separator or not _KEY.fullmatch(name):
        return None
    return name, _parse_value(raw.strip())


def _parse_value(raw: str) -> str:
    if raw.startswith('"'):
        return _double_quoted(raw[1:])
    if raw.startswith("'"):
        # Literal: no escapes. An unterminated quote keeps the rest of the line.
        return raw[1:].partition("'")[0]
    # A `#` starts a comment only after a space: a URL may contain one.
    return re.split(r"\s#", raw, maxsplit=1)[0].rstrip()


def _double_quoted(rest: str) -> str:
    out: list[str] = []
    chars = iter(rest)
    for char in chars:
        if char == '"':
            break
        if char == "\\":
            following = next(chars, "")
            out.append(_ESCAPES.get(following, "\\" + following))
        else:
            out.append(char)
    return "".join(out)
