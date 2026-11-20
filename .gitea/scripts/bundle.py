"""Pack what the build produced into the file the platform stores.

Usage: bundle.py miniapp --version 1.2.3 --out dist-ci     -> dist-ci/miniapp-1.2.3.base64.gz (the index.base64.gz of miniapp.out)
       bundle.py plugin  --version 1.2.3 --out dist-ci     -> dist-ci/plugin-1.2.3.mjs (the one ES module the backoffice loads)
Prints the path of the file written. Reads miniapp.yaml of the current directory (the repository root).
The mini-app file is the one `up-sdk build` writes next to dist/index.html: gzip(base64(the single-file HTML)). The shell and the web
launcher read exactly that format, and the platform stores the file as it is (its SHA-256 is the artifact checksum), so it is checked and
copied, never rebuilt.
Refuses a symbolic link anywhere on the way, a path that leaves the repository, an output folder inside the sources, a hard link,
a mini-app file that is not a complete gzip of base64 of UTF-8 text (or is over MAX_COMPRESSED_BYTES compressed, MAX_HTML_BYTES decoded),
more than MAX_PLUGIN_BYTES for the plugin module, and a target file that is a symbolic link.
"""

import argparse
import base64
import binascii
import os
import re
import shutil
import sys
import zlib
from pathlib import Path
from typing import Any

import miniapp_config

MINIAPP_FILE = "index.base64.gz"  # written by `up-sdk build`, read by the shell and the web launcher
MAX_COMPRESSED_BYTES = 18 * 1024 * 1024  # what is uploaded: the organisation API refuses a request body over 20 MB
MAX_HTML_BYTES = 64 * 1024 * 1024  # the HTML once decoded: the web launcher refuses more
MAX_PLUGIN_BYTES = 5 * 1024 * 1024  # the one ES module of a plugin: the organisation API refuses more (maxBackofficePluginSize)
_WHITESPACE = re.compile(rb"\s+")


def _inside_repository(relative: str, root: Path, what: str) -> Path:
    """The path under root, with no symbolic link on any component, staying inside root."""
    current = root
    for part in Path(relative).parts:
        current = current / part
        if current.is_symlink():
            raise miniapp_config.ConfigError(f"{what}: {relative} goes through a symbolic link")
    resolved = current.resolve()
    if not resolved.is_relative_to(root):
        raise miniapp_config.ConfigError(f"{what}: {relative} leaves the repository")
    return resolved


def _output_folder(out_dir: Path, root: Path, sources: list[Path]) -> Path:
    target = out_dir.resolve() if out_dir.is_absolute() else (root / out_dir).resolve()
    if not target.is_relative_to(root) or target == root:
        raise miniapp_config.ConfigError("the output folder must be a folder inside the repository")
    for source in sources:
        if target.is_relative_to(source) or source.is_relative_to(target):
            raise miniapp_config.ConfigError("the output folder must not overlap the sources")
    return target


def _open_new(target: Path) -> int:
    """A new regular file at target: an existing file is replaced, a symbolic link is refused and never followed."""
    if target.is_symlink():
        raise miniapp_config.ConfigError(f"{target.name} is a symbolic link: refusing to write through it")
    if target.exists():
        target.unlink()
    return os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)


def _check_miniapp_file(data: bytes) -> None:
    """The bytes are one complete gzip stream of base64 text that decodes to non-empty UTF-8 HTML (what the launcher decodes)."""
    if data[:2] != b"\x1f\x8b":
        raise miniapp_config.ConfigError(f"miniapp: {MINIAPP_FILE} is not a gzip file")
    limit = MAX_HTML_BYTES * 4 // 3 + 16  # base64 text of the largest accepted HTML
    inflater = zlib.decompressobj(16 + zlib.MAX_WBITS)
    try:
        text = inflater.decompress(data, limit + 1)
        complete = inflater.eof and not inflater.unused_data
    except zlib.error as error:
        raise miniapp_config.ConfigError(f"miniapp: {MINIAPP_FILE} is not a valid gzip file ({error})") from None
    if len(text) > limit or inflater.unconsumed_tail:
        raise miniapp_config.ConfigError(f"miniapp: {MINIAPP_FILE} holds more than {MAX_HTML_BYTES // (1024 * 1024)} MB of HTML")
    if not complete:
        raise miniapp_config.ConfigError(f"miniapp: {MINIAPP_FILE} is a truncated gzip file or has data after the gzip stream")
    try:
        html = base64.b64decode(_WHITESPACE.sub(b"", text), validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        raise miniapp_config.ConfigError(f"miniapp: {MINIAPP_FILE} does not hold the base64 of UTF-8 HTML") from None
    if not html.strip():
        raise miniapp_config.ConfigError(f"miniapp: {MINIAPP_FILE} holds an empty page")
    if len(html.encode("utf-8")) > MAX_HTML_BYTES:
        raise miniapp_config.ConfigError(f"miniapp: {MINIAPP_FILE} holds more than {MAX_HTML_BYTES // (1024 * 1024)} MB of HTML")


def pack_miniapp(config: dict[str, Any], version: str, out_dir: Path, root: Path | None = None) -> Path:
    miniapp_config.check_version(version)
    root = (root or Path.cwd()).resolve()
    section = config["miniapp"]
    relative = f"{section['dir']}/{section['out']}/{MINIAPP_FILE}"
    folder = _inside_repository(f"{section['dir']}/{section['out']}", root, "miniapp.out")
    source = _inside_repository(relative, root, "miniapp.out")
    target_dir = _output_folder(out_dir, root, [folder])
    if not source.is_file():
        raise miniapp_config.ConfigError(
            f"miniapp: the build did not write {MINIAPP_FILE} in {section['dir']}/{section['out']}: "
            "the miniapp build must run `up-sdk build` (npm run build of a mini-app made with @cloudparse/up-miniapps-sdk)"
        )
    info = source.lstat()
    if info.st_nlink > 1:
        raise miniapp_config.ConfigError(f"miniapp: {relative} is a hard link")
    if info.st_size == 0:
        raise miniapp_config.ConfigError(f"miniapp: {relative} is empty")
    if info.st_size > MAX_COMPRESSED_BYTES:
        raise miniapp_config.ConfigError(f"miniapp: {relative} is more than {MAX_COMPRESSED_BYTES // (1024 * 1024)} MB")
    data = source.read_bytes()
    _check_miniapp_file(data)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"miniapp-{version}.base64.gz"
    with os.fdopen(_open_new(target), "wb") as dst:
        dst.write(data)
    return target


def pack_plugin(config: dict[str, Any], version: str, out_dir: Path, root: Path | None = None) -> Path:
    miniapp_config.check_version(version)
    root = (root or Path.cwd()).resolve()
    section = config["plugin"]
    relative = f"{section['dir']}/{section['out']}/{section['file']}"
    source = _inside_repository(relative, root, "plugin.file")
    target_dir = _output_folder(out_dir, root, [source.parent])
    if not source.is_file() or source.stat().st_size == 0:
        raise miniapp_config.ConfigError(f"plugin: the build did not produce {relative}")
    if source.stat().st_nlink > 1:
        raise miniapp_config.ConfigError(f"plugin: {relative} is a hard link")
    if source.stat().st_size > MAX_PLUGIN_BYTES:
        raise miniapp_config.ConfigError(f"plugin: {relative} is more than {MAX_PLUGIN_BYTES // (1024 * 1024)} MB")
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"plugin-{version}{source.suffix}"
    with open(source, "rb") as src, os.fdopen(_open_new(target), "wb") as dst:
        shutil.copyfileobj(src, dst)
    return target


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("kind", choices=("miniapp", "plugin"))
    parser.add_argument("--version", required=True)
    parser.add_argument("--out", type=Path, default=Path("dist-ci"))
    parser.add_argument("--config", default="miniapp.yaml")
    args = parser.parse_args(argv)
    try:
        config = miniapp_config.load(Path(args.config))
        miniapp_config.validate(config)
        pack = pack_miniapp if args.kind == "miniapp" else pack_plugin
        print(pack(config, args.version, args.out))
    except miniapp_config.ConfigError as error:
        print(f"bundle: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
