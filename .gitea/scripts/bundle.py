"""Pack what the build produced into the file the platform stores.

Usage: bundle.py miniapp --version 1.2.3 --out dist-ci     -> dist-ci/miniapp-1.2.3.tar.gz (the content of miniapp.out)
       bundle.py plugin  --version 1.2.3 --out dist-ci     -> dist-ci/plugin-1.2.3.mjs (the one ES module the backoffice loads)
Prints the path of the file written. Reads miniapp.yaml of the current directory (the repository root).
Refuses a symbolic link anywhere on the way, a path that leaves the repository, and an output folder inside the sources.
"""

import argparse
import shutil
import stat
import sys
import tarfile
from pathlib import Path
from typing import Any

import miniapp_config

MAX_FILES = 20000


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


def _fixed(info: tarfile.TarInfo) -> tarfile.TarInfo:
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    info.mtime = 0
    info.mode = 0o755 if info.isdir() else 0o644
    return info


def pack_miniapp(config: dict[str, Any], version: str, out_dir: Path, root: Path | None = None) -> Path:
    miniapp_config.check_version(version)
    root = (root or Path.cwd()).resolve()
    section = config["miniapp"]
    source = _inside_repository(f"{section['dir']}/{section['out']}", root, "miniapp.out")
    target_dir = _output_folder(out_dir, root, [source])
    if not source.is_dir() or not any(source.iterdir()):
        raise miniapp_config.ConfigError(f"miniapp: the build produced nothing in {section['dir']}/{section['out']}")
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"miniapp-{version}.tar.gz"
    entries = sorted(source.rglob("*"))
    if len(entries) > MAX_FILES:
        raise miniapp_config.ConfigError(f"miniapp: more than {MAX_FILES} files in the build output")
    with tarfile.open(target, "w:gz") as archive:
        for entry in entries:
            mode = entry.lstat().st_mode
            if stat.S_ISLNK(mode) or not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
                raise miniapp_config.ConfigError(f"miniapp: {entry.relative_to(source)} is not a regular file or folder")
            archive.add(entry, arcname=entry.relative_to(source).as_posix(), recursive=False, filter=_fixed)
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
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"plugin-{version}{source.suffix}"
    shutil.copyfile(source, target)
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
