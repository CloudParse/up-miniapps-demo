"""Read and validate miniapp.yaml (format: miniapp.schema.json) with the standard library only.

The CI runner has Python but no PyYAML, so this reads the small YAML subset the platform and the docs use:
nested mappings (two-space indent), scalars, quoted strings, flow lists `[a, b]` and block lists `- a`.
Anything else (anchors, multi-line strings, tabs) is refused with a clear message.

Usage: miniapp_config.py validate [--file miniapp.yaml]
       miniapp_config.py plan --target backend|frontend|plugin [--file miniapp.yaml]
           prints `run`, or `skip <reason>` when the section of that target is absent (never an error);
           an invalid file is an error
       miniapp_config.py get <dotted.key> [--file miniapp.yaml]   (prints the value; a list prints one item per line)
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Any

SLUG = re.compile(r"^[a-z]([a-z0-9-]{0,18}[a-z0-9])?$")
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
REL_PATH = re.compile(r"^(?!/)(?!.*\.\.)[A-Za-z0-9._/-]+$")
HEALTH_PATH = re.compile(r"^/[A-Za-z0-9._~/%-]*$")
JS_FILE = re.compile(r"^(?!/)(?!.*\.\.)[A-Za-z0-9._/-]+\.m?js$")
SERVICES = ("postgres", "cache", "bucket")
SECTION_OF_TARGET = {"backend": "api", "frontend": "miniapp", "plugin": "plugin"}
TARGETS = tuple(SECTION_OF_TARGET)


class ConfigError(ValueError):
    """The file is not a valid miniapp.yaml."""


def _strip_comment(line: str) -> str:
    quote = ""
    for index, char in enumerate(line):
        if quote:
            if char == quote:
                quote = ""
        elif char in "\"'":
            quote = char
        elif char == "#" and (index == 0 or line[index - 1] in " \t"):
            return line[:index]
    return line


def _scalar(raw: str) -> Any:
    text = raw.strip()
    if not text:
        return None
    if text[0] in "\"'":
        if len(text) < 2 or text[-1] != text[0]:
            raise ConfigError(f"unterminated quoted string: {raw!r}")
        return text[1:-1]
    if text.startswith("["):
        if not text.endswith("]"):
            raise ConfigError(f"unterminated list: {raw!r}")
        return _flow_list(text[1:-1])
    if text[0] in "&*!|>{%@`":
        raise ConfigError(f"unsupported YAML syntax: {raw!r}")
    if text in ("true", "false"):
        return text == "true"
    if text in ("null", "~"):
        return None
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    return text


def _flow_list(inner: str) -> list[Any]:
    items: list[str] = []
    current, quote = "", ""
    for char in inner:
        if quote:
            current += char
            if char == quote:
                quote = ""
        elif char in "\"'":
            quote = char
            current += char
        elif char == ",":
            items.append(current)
            current = ""
        else:
            current += char
    if current.strip() or items:
        items.append(current)
    return [_scalar(item) for item in items if item.strip()]


def parse(text: str) -> dict[str, Any]:
    """Parse the YAML subset into nested dicts, lists and scalars."""
    lines: list[tuple[int, str, int]] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        if "\t" in raw:
            raise ConfigError(f"line {number}: tabs are not allowed, indent with two spaces")
        stripped = _strip_comment(raw).rstrip()
        if not stripped.strip():
            continue
        indent = len(stripped) - len(stripped.lstrip(" "))
        lines.append((indent, stripped.strip(), number))
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
        key, separator, rest = content.partition(":")
        if not separator or not key or " " in key.strip():
            raise ConfigError(f"line {number}: expected `key: value`, got {content!r}")
        key = key.strip()
        if key in mapping:
            raise ConfigError(f"line {number}: duplicate key {key!r}")
        position += 1
        if rest.strip():
            mapping[key] = _scalar(rest)
        elif position < len(lines) and lines[position][0] > indent:
            mapping[key], position = _block(lines, position, lines[position][0])
        else:
            mapping[key] = None
    return mapping, position


def _block_list(lines: list[tuple[int, str, int]], position: int, indent: int) -> tuple[list[Any], int]:
    items: list[Any] = []
    while position < len(lines) and lines[position][0] == indent and lines[position][1].startswith("- "):
        items.append(_scalar(lines[position][1][2:]))
        position += 1
    return items, position


def load(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise ConfigError(f"cannot read {path}: {error.strerror}") from error
    return parse(text)


def _section(config: dict[str, Any], name: str, allowed: tuple[str, ...], required: tuple[str, ...]) -> dict[str, Any]:
    value = config.get(name)
    if not isinstance(value, dict):
        raise ConfigError(f"{name}: must be a mapping")
    unknown = sorted(set(value) - set(allowed))
    if unknown:
        raise ConfigError(f"{name}: unknown key {unknown[0]!r}")
    for key in required:
        if value.get(key) in (None, ""):
            raise ConfigError(f"{name}.{key}: required")
    return value


def _check_path(section: str, key: str, value: Any, pattern: re.Pattern[str] = REL_PATH) -> None:
    if not isinstance(value, str) or not pattern.match(value):
        raise ConfigError(f"{section}.{key}: must be a relative path without '..'")


def _check_build(section: str, value: dict[str, Any]) -> None:
    build = value["build"]
    if not isinstance(build, str) or not 1 <= len(build) <= 500:
        raise ConfigError(f"{section}.build: must be a command of 1 to 500 characters")
    _check_path(section, "dir", value["dir"])
    _check_path(section, "out", value["out"])


def _check_api(api: dict[str, Any]) -> None:
    _check_path("api", "dir", api["dir"])
    port = api["port"]
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise ConfigError("api.port: must be an integer from 1 to 65535")
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


def validate(config: dict[str, Any]) -> None:
    """Raise ConfigError with a message the developer can act on."""
    if config.get("version") not in (1, 2):
        raise ConfigError("version: must be 1 or 2")
    if not isinstance(config.get("uuid"), str) or not UUID.match(config["uuid"]):
        raise ConfigError("uuid: must be the mini-app uuid")
    if not isinstance(config.get("slug"), str) or not SLUG.match(config["slug"]):
        raise ConfigError("slug: must be the mini-app slug")
    if not isinstance(config.get("name"), str) or not config["name"]:
        raise ConfigError("name: required")
    deployable = [name for name in ("api", "services", "miniapp", "plugin") if name in config]
    if config["version"] == 1 and deployable:
        raise ConfigError(f"{deployable[0]}: needs `version: 2`")
    if "api" in config:
        _check_api(_section(config, "api", ("dir", "port", "healthPath", "command", "publicIngress"), ("dir", "port")))
    if "services" in config:
        services = _section(config, "services", SERVICES, ())
        if "api" not in config:
            raise ConfigError("services: needs an api section")
        for name, flag in services.items():
            if not isinstance(flag, bool):
                raise ConfigError(f"services.{name}: must be true or false")
    for name in ("miniapp", "plugin"):
        if name in config:
            required = ("dir", "build", "out") + (("file",) if name == "plugin" else ())
            section = _section(config, name, required, required)
            _check_build(name, section)
    if "plugin" in config and not JS_FILE.match(str(config["plugin"]["file"])):
        raise ConfigError("plugin.file: must be a .js or .mjs file, relative to out")


def plan(config: dict[str, Any], target: str) -> str:
    """`run` when the target's section exists, else `skip <reason>`; the file is validated first."""
    if target not in TARGETS:
        raise ConfigError(f"target must be one of {', '.join(TARGETS)}")
    validate(config)
    section = SECTION_OF_TARGET[target]
    if section in config:
        return "run"
    return f"skip miniapp.yaml has no `{section}` section: nothing to deploy for the {target} (add it with `version: 2`, or delete this workflow)"


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
            print(_format(get(config, args.key)))
    except ConfigError as error:
        print(f"miniapp.yaml: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
