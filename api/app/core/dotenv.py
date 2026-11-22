"""Minimal ``.env`` loader for the development entry point (standard library only).

``uv run --env-file .env python -m app`` loads the file before Python starts. A plain
``python -m app`` does not, and the API then silently falls back to the defaults of
``configs/config.toml``. This loader makes both commands give the same result.

It reads ``KEY=VALUE`` lines. It never overrides a variable that is already in the
environment, so a real shell variable (or the production container) always wins.
Values are never logged: a skipped line is reported by its number only.
Not supported (so ``uv --env-file`` is not identical beyond plain values):
``$VAR`` expansion and multi-line values.
"""

import logging
import os
import re
from collections.abc import MutableMapping
from pathlib import Path

logger = logging.getLogger(__name__)

_EXPORT = re.compile(r"export\s+")
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
    # utf-8-sig: an editor may write a BOM. Split on "\n" only: str.splitlines()
    # also cuts at U+2028 and others, which may sit inside a quoted value.
    text = path.read_text(encoding="utf-8-sig")
    for number, line in enumerate(text.split("\n"), start=1):
        line = line.removesuffix("\r")
        parsed = _parse_line(line)
        if parsed is None:
            if _is_skipped(line):
                # The line number only: the line may hold a secret.
                logger.warning(
                    "%s: line %d is not KEY=VALUE, skipped", path.name, number
                )
            continue
        name, value = parsed
        if name in target:
            if target[name] != value:
                # Names only, never values.
                logger.warning(
                    "%s is already set in the environment and differs from %s: "
                    "the environment wins",
                    name,
                    path.name,
                )
            continue
        target[name] = value
        loaded.append(name)
    return loaded


def _is_skipped(line: str) -> bool:
    text = line.strip()
    return bool(text) and not text.startswith("#")


def _parse_line(line: str) -> tuple[str, str] | None:
    text = line.strip()
    if not text or text.startswith("#"):
        return None
    text = _EXPORT.sub("", text, count=1)
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
