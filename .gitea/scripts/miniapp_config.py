"""Read and validate miniapp.yaml (format: miniapp.schema.json) with the standard library only.

The CI runner has Python but no PyYAML, so this reads a small, strict YAML subset: nested mappings (two-space indent), plain
or quoted scalars, flow lists `[a, b]` and block lists `- a`. Everything else is refused, never guessed: an anchor, a
multi-line string, a quoted key, a backslash escape, a tab, any control character (including the Unicode line separators
U+0085, U+2028 and U+2029). A file that is not valid makes the run FAIL; it is never read as "nothing to do".

Usage: miniapp_config.py validate [--file miniapp.yaml]
       miniapp_config.py plan --target backend|frontend|plugin [--file miniapp.yaml]
           prints `run`, or `skip <reason>` when the section of that target is absent;
           an invalid file exits with an error
       miniapp_config.py get <dotted.key> [--file miniapp.yaml]   (prints the value; a list prints one item per line)
"""

import argparse
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

# One path segment: no leading '-', not '.', '..', '.git' or 'dist-ci' (the CI's own output folder).
_SEGMENT = r"(?!-)(?!(?:\.{1,2}|\.git|dist-ci)(?:/|$))[A-Za-z0-9._-]+"
REL_PATH_PATTERN = rf"^{_SEGMENT}(?:/{_SEGMENT})*$"
JS_FILE_PATTERN = rf"^(?=.*\.m?js$){_SEGMENT}(?:/{_SEGMENT})*$"
HEALTH_PATTERN = r"^/[A-Za-z0-9._~/%-]*$"
VERSION_PATTERN = r"(0|[1-9][0-9]{0,8})\.(0|[1-9][0-9]{0,8})\.(0|[1-9][0-9]{0,8})"

SLUG = re.compile(r"^[a-z]([a-z0-9-]{0,18}[a-z0-9])?$")
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
REL_PATH = re.compile(REL_PATH_PATTERN)
HEALTH_PATH = re.compile(HEALTH_PATTERN)
JS_FILE = re.compile(JS_FILE_PATTERN)
LOGO = re.compile(rf"^(?=.*\.webp$){_SEGMENT}(?:/{_SEGMENT})*$")
VERSION = re.compile(VERSION_PATTERN)
KEY = re.compile(r"^([A-Za-z][A-Za-z0-9]*):(?: +(.*))?$")

CARD_STYLES = ("navy", "blush", "night", "mist", "violet")
DEVICE_TYPES = ("PHONE", "TABLET", "DESKTOP", "TV")
SERVICES = ("postgres", "cache", "bucket")
MIN_PORT = 1024  # the image runs as a non-root user

SECTION_KEYS: dict[str, tuple[str, ...]] = {
    "api": ("dir", "port", "healthPath", "command", "publicIngress"),
    "services": SERVICES,
    "miniapp": ("dir", "build", "out"),
    "plugin": ("dir", "build", "out", "file"),
}
TOP_LEVEL_KEYS = (
    "version", "uuid", "slug", "name", "description", "logo", "cardStyle", "darkTheme", "deviceTypes",
    *SECTION_KEYS,
)
SECTION_OF_TARGET = {"backend": "api", "frontend": "miniapp", "plugin": "plugin"}
TARGETS = tuple(SECTION_OF_TARGET)
MAX_DESCRIPTION = 2000


class ConfigError(ValueError):
    """The file is not a valid miniapp.yaml."""


def check_version(version: str) -> str:
    """Return version when it is a strict semver `X.Y.Z` (no sign, no leading zero, nothing else)."""
    if not isinstance(version, str) or not VERSION.fullmatch(version):
        raise ConfigError("version must be a plain semver such as 1.2.3")
    return version


def check_uuid(value: str) -> str:
    if not isinstance(value, str) or not UUID.match(value):
        raise ConfigError("uuid: must be the mini-app uuid")
    return value


def _check_characters(text: str) -> None:
    for number, line in enumerate(text.split("\n"), start=1):
        body = line[:-1] if line.endswith("\r") else line
        for char in body:
            if unicodedata.category(char) in ("Cc", "Cf", "Zl", "Zp", "Cs", "Co", "Cn"):
                raise ConfigError(f"line {number}: control character U+{ord(char):04X} is not allowed")


def _split_lines(text: str) -> list[tuple[int, str, int]]:
    """Split on \\n and \\r\\n only; returns (indent, content, line number) of every line that is not blank or a comment."""
    _check_characters(text)
    lines: list[tuple[int, str, int]] = []
    for number, raw in enumerate(text.split("\n"), start=1):
        line = raw[:-1] if raw.endswith("\r") else raw
        content = line.lstrip(" ")
        if not content.strip() or content.startswith("#"):
            continue
        indent = len(line) - len(content)
        if indent % 2:
            raise ConfigError(f"line {number}: indent with two spaces per level")
        lines.append((indent, content, number))
    return lines


def _tail_is_comment(tail: str, number: int) -> None:
    if tail.strip() and not (tail[:1] in (" ",) and tail.lstrip().startswith("#")):
        raise ConfigError(f"line {number}: unexpected text after the value")


def _quoted(text: str, number: int) -> tuple[str, str]:
    quote = text[0]
    end = text.find(quote, 1)
    if end < 0:
        raise ConfigError(f"line {number}: unterminated quoted string")
    body = text[1:end]
    if "\\" in body:
        raise ConfigError(f"line {number}: backslash escapes are not supported, remove the backslash")
    return body, text[end + 1 :]


def _plain(text: str, number: int) -> Any:
    if text[0] in "&*!|>{%@`?":
        raise ConfigError(f"line {number}: unsupported YAML syntax {text[0]!r}")
    if '"' in text or "'" in text:
        raise ConfigError(f"line {number}: quote the whole value, or remove the quote")
    if ": " in text or text.endswith(":"):
        raise ConfigError(f"line {number}: a value cannot hold ': ' (quote it)")
    if text in ("true", "false"):
        return text == "true"
    if text in ("null", "~"):
        return None
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    return text


def _flow_list(text: str, number: int) -> tuple[list[Any], str]:
    items: list[Any] = []
    position = 1
    while True:
        while position < len(text) and text[position] == " ":
            position += 1
        if position >= len(text):
            raise ConfigError(f"line {number}: unterminated list")
        if text[position] == "]":
            return items, text[position + 1 :]
        if text[position] in "\"'":
            body, rest = _quoted(text[position:], number)
            items.append(body)
            position = len(text) - len(rest)
        else:
            end = position
            while end < len(text) and text[end] not in ",]":
                end += 1
            token = text[position:end].strip()
            if not token or "[" in token or " #" in token:
                raise ConfigError(f"line {number}: invalid list item {token!r}")
            items.append(_plain(token, number))
            position = end
        while position < len(text) and text[position] == " ":
            position += 1
        if position < len(text) and text[position] == ",":
            position += 1
        elif position >= len(text) or text[position] != "]":
            raise ConfigError(f"line {number}: expected ',' or ']'")


def _value(raw: str, number: int) -> Any:
    """Parse what follows `key:` or `- `; returns the sentinel _EMPTY when there is nothing but a comment."""
    text = raw.strip(" ")
    if not text or text.startswith("#"):
        return _EMPTY
    if text[0] in "\"'":
        body, tail = _quoted(text, number)
        _tail_is_comment(tail, number)
        return body
    if text[0] == "[":
        items, tail = _flow_list(text, number)
        _tail_is_comment(tail, number)
        return items
    cut = re.search(r" #", text)
    return _plain(text[: cut.start()].rstrip() if cut else text, number)


_EMPTY = object()


def parse(text: str) -> dict[str, Any]:
    """Parse the YAML subset into nested dicts, lists and scalars."""
    lines = _split_lines(text)
    result, position = _block(lines, 0, 0)
    if position != len(lines):
        raise ConfigError(f"line {lines[position][2]}: unexpected indentation")
    if not isinstance(result, dict):
        raise ConfigError("the file must be a mapping")
    return result


def _block(lines: list[tuple[int, str, int]], position: int, indent: int) -> tuple[Any, int]:
    if position < len(lines) and lines[position][1].startswith("- "):
        return _block_list(lines, position, indent)
    mapping: dict[str, Any] = {}
    while position < len(lines):
        line_indent, content, number = lines[position]
        if line_indent < indent:
            break
        if line_indent > indent:
            raise ConfigError(f"line {number}: unexpected indentation")
        match = KEY.match(content)
        if not match:
            raise ConfigError(f"line {number}: expected `key: value` (a plain key, a colon, a space), got {content!r}")
        key, rest = match.group(1), match.group(2) or ""
        if key in mapping:
            raise ConfigError(f"line {number}: duplicate key {key!r}")
        position += 1
        value = _value(rest, number)
        if value is not _EMPTY:
            mapping[key] = value
        elif position < len(lines) and lines[position][0] > indent:
            mapping[key], position = _block(lines, position, lines[position][0])
        else:
            mapping[key] = None
    return mapping, position


def _block_list(lines: list[tuple[int, str, int]], position: int, indent: int) -> tuple[list[Any], int]:
    items: list[Any] = []
    while position < len(lines) and lines[position][0] == indent and lines[position][1].startswith("- "):
        value = _value(lines[position][1][2:], lines[position][2])
        if value is _EMPTY:
            raise ConfigError(f"line {lines[position][2]}: empty list item")
        items.append(value)
        position += 1
    return items, position


def load(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise ConfigError(f"cannot read {path}: {error.strerror}") from error
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ConfigError(f"{path} is not valid UTF-8") from error
    return parse(text)


def _section(config: dict[str, Any], name: str, required: tuple[str, ...]) -> dict[str, Any]:
    value = config.get(name)
    if not isinstance(value, dict):
        raise ConfigError(f"{name}: must be a mapping")
    unknown = sorted(set(value) - set(SECTION_KEYS[name]))
    if unknown:
        raise ConfigError(f"{name}: unknown key {unknown[0]!r}")
    for key in required:
        if value.get(key) in (None, ""):
            raise ConfigError(f"{name}.{key}: required")
    return value


def _check_path(section: str, key: str, value: Any, pattern: re.Pattern[str] = REL_PATH) -> None:
    if not isinstance(value, str) or not pattern.match(value):
        raise ConfigError(
            f"{section}.{key}: must be a relative path of plain segments (no leading '/', '-', '.', '..', '.git', 'dist-ci' or '//')"
        )


def _check_build(section: str, value: dict[str, Any]) -> None:
    build = value["build"]
    if not isinstance(build, str) or not 1 <= len(build) <= 500:
        raise ConfigError(f"{section}.build: must be a command of 1 to 500 characters")
    _check_path(section, "dir", value["dir"])
    _check_path(section, "out", value["out"])


def _check_api(api: dict[str, Any]) -> None:
    _check_path("api", "dir", api["dir"])
    port = api["port"]
    if isinstance(port, bool) or not isinstance(port, int) or not MIN_PORT <= port <= 65535:
        raise ConfigError(f"api.port: must be an integer from {MIN_PORT} to 65535")
    health = api.get("healthPath")
    if health is not None and (not isinstance(health, str) or not HEALTH_PATH.match(health)):
        raise ConfigError("api.healthPath: must be a path starting with '/'")
    command = api.get("command")
    if command is not None and (
        not isinstance(command, list)
        or not 1 <= len(command) <= 16
        or not all(isinstance(item, str) and 1 <= len(item) <= 255 for item in command)
    ):
        raise ConfigError("api.command: must be a list of 1 to 16 non-empty strings")
    if "publicIngress" in api and not isinstance(api["publicIngress"], bool):
        raise ConfigError("api.publicIngress: must be true or false")


def _check_identity(config: dict[str, Any]) -> None:
    if config.get("version") not in (1, 2) or isinstance(config.get("version"), bool):
        raise ConfigError("version: must be 1 or 2")
    if not isinstance(config.get("uuid"), str) or not UUID.match(config["uuid"]):
        raise ConfigError("uuid: must be the mini-app uuid")
    if not isinstance(config.get("slug"), str) or not SLUG.match(config["slug"]):
        raise ConfigError("slug: must be the mini-app slug")
    if not isinstance(config.get("name"), str) or not config["name"]:
        raise ConfigError("name: required")
    if config.get("description") is not None and (
        not isinstance(config["description"], str) or len(config["description"]) > MAX_DESCRIPTION
    ):
        raise ConfigError("description: must be a text")
    logo = config.get("logo")
    if logo is not None and (not isinstance(logo, str) or not LOGO.match(logo)):
        raise ConfigError("logo: must be a .webp path of this repository, or null")
    if config.get("cardStyle") is not None and config["cardStyle"] not in CARD_STYLES:
        raise ConfigError(f"cardStyle: must be one of {', '.join(CARD_STYLES)}")
    if config.get("darkTheme") is not None and not isinstance(config["darkTheme"], bool):
        raise ConfigError("darkTheme: must be true, false or null")
    devices = config.get("deviceTypes")
    if devices is not None and (
        not isinstance(devices, list) or not devices or len(set(devices)) != len(devices)
        or not all(device in DEVICE_TYPES for device in devices)
    ):
        raise ConfigError(f"deviceTypes: one or more of {', '.join(DEVICE_TYPES)}, each once")


def validate(config: dict[str, Any]) -> None:
    """Raise ConfigError with a message the developer can act on."""
    unknown = sorted(set(config) - set(TOP_LEVEL_KEYS))
    if unknown:
        raise ConfigError(f"{unknown[0]}: unknown key (allowed: {', '.join(TOP_LEVEL_KEYS)})")
    _check_identity(config)
    deployable = [name for name in SECTION_KEYS if name in config]
    if config["version"] == 1 and deployable:
        raise ConfigError(f"{deployable[0]}: needs `version: 2`")
    if "api" in config:
        _check_api(_section(config, "api", ("dir", "port")))
    if "services" in config:
        services = _section(config, "services", ())
        if "api" not in config:
            raise ConfigError("services: needs an api section")
        for name, flag in services.items():
            if not isinstance(flag, bool):
                raise ConfigError(f"services.{name}: must be true or false")
    for name in ("miniapp", "plugin"):
        if name in config:
            _check_build(name, _section(config, name, SECTION_KEYS[name]))
    if "plugin" in config:
        _check_path("plugin", "file", config["plugin"]["file"], JS_FILE)


def plan(config: dict[str, Any], target: str) -> str:
    """`run` when the target's section exists, else `skip <reason>`; the file is validated first (invalid = error)."""
    if target not in TARGETS:
        raise ConfigError(f"target must be one of {', '.join(TARGETS)}")
    validate(config)
    section = SECTION_OF_TARGET[target]
    if section in config:
        return "run"
    return (
        f"skip miniapp.yaml has no `{section}` section: nothing to deploy for the {target}. "
        "Add the section with `version: 2`, or delete this workflow."
    )


def get(config: dict[str, Any], dotted: str) -> Any:
    value: Any = config
    for part in dotted.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def _format(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return "\n".join(str(item) for item in value)
    return str(value)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("validate")
    check.add_argument("--file", default="miniapp.yaml")
    planned = sub.add_parser("plan")
    planned.add_argument("--target", choices=TARGETS, required=True)
    planned.add_argument("--file", default="miniapp.yaml")
    read = sub.add_parser("get")
    read.add_argument("key")
    read.add_argument("--file", default="miniapp.yaml")
    args = parser.parse_args(argv)
    try:
        config = load(Path(args.file))
        if args.command == "validate":
            validate(config)
        elif args.command == "plan":
            print(plan(config, args.target))
        else:
            validate(config)
            print(_format(get(config, args.key)))
    except ConfigError as error:
        print(f"miniapp.yaml: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
