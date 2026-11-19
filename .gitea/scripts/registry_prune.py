"""Keep only the image of the current version in the Gitea container registry (the latest image is the only one shown).

Environment: GITEA_SERVER_URL, REGISTRY_USER, REGISTRY_TOKEN (a token with write:package).
Usage: registry_prune.py --owner <owner> --name <package> --keep-version 1.2.3
"""

import argparse
import base64
import os
import sys
import urllib.parse
from typing import Any

import ci_http

PAGE_SIZE = 50
MAX_PAGES = 20


def _basic_auth() -> str:
    user, token = os.environ.get("REGISTRY_USER", ""), os.environ.get("REGISTRY_TOKEN", "")
    if not user or not token:
        raise ci_http.ApiError(0, "REGISTRY_USER and REGISTRY_TOKEN are not set")
    return base64.b64encode(f"{user}:{token}".encode()).decode()


def list_versions(server: str, owner: str, name: str, auth: str) -> list[dict[str, Any]]:
    versions: list[dict[str, Any]] = []
    for page in range(1, MAX_PAGES + 1):
        query = urllib.parse.urlencode({"type": "container", "q": name, "limit": PAGE_SIZE, "page": page})
        batch = ci_http.request_json("GET", f"{server}/api/v1/packages/{urllib.parse.quote(owner)}?{query}", basic=auth)
        if not batch:
            break
        versions.extend(item for item in batch if item.get("name") == name)
        if len(batch) < PAGE_SIZE:
            break
    return versions


def prune(server: str, owner: str, name: str, keep_version: str, auth: str) -> list[str]:
    """Delete every version of the package except keep_version; returns the versions deleted."""
    removed: list[str] = []
    for item in list_versions(server, owner, name, auth):
        version = str(item["version"])
        if version == keep_version:
            continue
        path = f"{urllib.parse.quote(owner)}/container/{urllib.parse.quote(name)}/{urllib.parse.quote(version)}"
        ci_http.request_json("DELETE", f"{server}/api/v1/packages/{path}", basic=auth)
        removed.append(version)
    return removed


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--keep-version", required=True)
    args = parser.parse_args(argv)
    try:
        server = os.environ.get("GITEA_SERVER_URL", "").rstrip("/")
        if not server:
            raise ci_http.ApiError(0, "GITEA_SERVER_URL is not set")
        removed = prune(server, args.owner.lower(), args.name.lower(), args.keep_version, _basic_auth())
    except ci_http.ApiError as error:
        print(f"registry_prune: {error}", file=sys.stderr)
        return 1
    print(f"registry: removed {', '.join(removed) if removed else 'nothing'}; kept {args.keep_version}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
