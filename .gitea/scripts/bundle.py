"""Pack what the build produced into the file the platform stores.

Usage: bundle.py miniapp --version 1.2.3 --out dist-ci     -> dist-ci/miniapp-1.2.3.tar.gz (the content of miniapp.out)
       bundle.py plugin  --version 1.2.3 --out dist-ci     -> dist-ci/plugin-1.2.3.mjs (the one ES module the backoffice loads)
Prints the path of the file written. Reads miniapp.yaml of the current directory.
"""

import argparse
import shutil
import sys
import tarfile
from pathlib import Path

import miniapp_config


def _fixed(info: tarfile.TarInfo) -> tarfile.TarInfo:
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    info.mtime = 0
    return info


def pack_miniapp(config: dict, version: str, out_dir: Path) -> Path:
    section = config["miniapp"]
    source = Path(section["dir"]) / section["out"]
    if not source.is_dir() or not any(source.iterdir()):
        raise miniapp_config.ConfigError(f"miniapp: the build produced nothing in {source}")
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"miniapp-{version}.tar.gz"
    with tarfile.open(target, "w:gz") as archive:
        for entry in sorted(source.rglob("*")):
            if entry.is_symlink():
                raise miniapp_config.ConfigError(f"miniapp: symbolic link in the build output: {entry}")
            archive.add(entry, arcname=entry.relative_to(source).as_posix(), recursive=False, filter=_fixed)
    return target


def pack_plugin(config: dict, version: str, out_dir: Path) -> Path:
    section = config["plugin"]
    source = Path(section["dir"]) / section["out"] / section["file"]
    if not source.is_file() or source.stat().st_size == 0:
        raise miniapp_config.ConfigError(f"plugin: the build did not produce {source}")
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"plugin-{version}{source.suffix}"
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
        pack = pack_miniapp if args.kind == "miniapp" else pack_plugin
        print(pack(config, args.version, args.out))
    except miniapp_config.ConfigError as error:
        print(f"bundle: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
