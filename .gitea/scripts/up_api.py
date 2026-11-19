"""Calls of the deployment CI to the organisation API, authenticated with the credentials of the mini-app.

Environment (Gitea Actions secrets, never arguments):
  UP_API_URL         base of the organisation API including /api/v1, e.g. https://api.<slug>.<domain>/api/v1
  UP_CLIENT_ID       client id of the mini-app
  UP_CLIENT_SECRET   client secret of the mini-app
The mini-app uuid comes from miniapp.yaml.

Usage: up_api.py publish miniapp|plugin --version 1.2.3 --file <path>
       up_api.py prune miniapp|plugin [--keep 5]   (miniapp: the organisation API's prune-old route; plugin: one by one)
       up_api.py deploy-component
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Any

import ci_http
import miniapp_config

KINDS = ("miniapp", "plugin")
MAX_PAGES = 20
PAGE_SIZE = 100
MIN_PRUNE_KEEP = 5  # the organisation API's prune-old refuses less


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ci_http.ApiError(0, f"{name} is not set: the platform writes it as an Actions secret of this repository")
    return value


class Client:
    def __init__(self, api_url: str, app_uuid: str, client_id: str, client_secret: str) -> None:
        self.api = api_url.rstrip("/")
        self.app_uuid = app_uuid
        self._credentials = {"clientId": client_id, "clientSecret": client_secret}
        self._token = ""

    @classmethod
    def from_env(cls, app_uuid: str) -> "Client":
        return cls(_env("UP_API_URL"), app_uuid, _env("UP_CLIENT_ID"), _env("UP_CLIENT_SECRET"))

    def token(self) -> str:
        if not self._token:
            answer = ci_http.request_json("POST", f"{self.api}/ci/token", self._credentials)
            token = answer.get("token") if isinstance(answer, dict) else None
            if not token:
                raise ci_http.ApiError(0, "the token endpoint answered without a token")
            self._token = str(token)
        return self._token

    def _list_url(self, kind: str) -> str:
        if kind == "miniapp":
            return f"{self.api}/admin/applications/{self.app_uuid}/artifacts"
        return f"{self.api}/admin/applications/{self.app_uuid}/backoffice-plugin/artifacts"

    def _delete_url(self, kind: str, artifact_uuid: str) -> str:
        if kind == "miniapp":
            return f"{self.api}/admin/applications/artifacts/{artifact_uuid}"
        return f"{self.api}/admin/backoffice-plugins/artifacts/{artifact_uuid}"

    def publish(self, kind: str, version: str, file_path: Path) -> Any:
        """Upload one bundle with an empty changelog; the plugin becomes the active one."""
        fields = {"version": version}
        if kind == "plugin":
            fields["activate"] = "true"
        body, content_type = ci_http.multipart(fields, "file", file_path.name, file_path.read_bytes())
        headers = {"Authorization": f"Bearer {self.token()}", "Content-Type": content_type, "Accept": "application/json"}
        return ci_http.request("POST", self._list_url(kind), headers=headers, body=body)

    def list_artifacts(self, kind: str) -> list[dict[str, Any]]:
        artifacts: list[dict[str, Any]] = []
        cursor = ""
        for _ in range(MAX_PAGES):
            url = f"{self._list_url(kind)}?limit={PAGE_SIZE}" + (f"&cursor={cursor}" if cursor else "")
            page = ci_http.request_json("GET", url, token=self.token())
            data = page.get("data") if isinstance(page, dict) else None
            if not data:
                break
            artifacts.extend(data)
            cursor = page.get("nextCursor") or ""
            if not cursor:
                break
        return artifacts

    def prune_old(self, keep: int) -> dict[str, int]:
        """Mini-app bundles: the organisation API's own route deletes every artifact beyond the `keep` newest of each app."""
        if keep < MIN_PRUNE_KEEP:
            raise ValueError(f"keep must be at least {MIN_PRUNE_KEEP}: the API refuses less")
        answer = ci_http.request_json("DELETE", f"{self.api}/admin/applications/artifacts/prune-old?keep={keep}", token=self.token())
        return answer if isinstance(answer, dict) else {}

    def prune(self, kind: str, keep: int) -> list[str]:
        """Plugin bundles: delete every one beyond the `keep` newest, one by one; returns the versions deleted."""
        if keep < 1:
            raise ValueError("keep must be at least 1")
        newest_first = sorted(self.list_artifacts(kind), key=lambda item: str(item.get("createdAt", "")), reverse=True)
        removed: list[str] = []
        for artifact in newest_first[keep:]:
            ci_http.request_json("DELETE", self._delete_url(kind, str(artifact["uuid"])), token=self.token())
            removed.append(str(artifact.get("version", "")))
        return removed

    def deploy_component(self) -> Any:
        """Roll out the custom component linked to the mini-app (the platform set its image tag before the run)."""
        url = f"{self.api}/admin/applications/{self.app_uuid}/custom-component/deploy"
        return ci_http.request_json("POST", url, {}, token=self.token())


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="miniapp.yaml")
    sub = parser.add_subparsers(dest="command", required=True)
    publish = sub.add_parser("publish")
    publish.add_argument("kind", choices=KINDS)
    publish.add_argument("--version", required=True)
    publish.add_argument("--file", required=True, type=Path)
    prune = sub.add_parser("prune")
    prune.add_argument("kind", choices=KINDS)
    prune.add_argument("--keep", type=int, default=MIN_PRUNE_KEEP)
    sub.add_parser("deploy-component")
    args = parser.parse_args(argv)
    try:
        config = miniapp_config.load(Path(args.config))
        client = Client.from_env(str(config.get("uuid", "")))
        if args.command == "publish":
            client.publish(args.kind, args.version, args.file)
            print(f"published {args.kind} {args.version}")
        elif args.command == "prune":
            if args.kind == "miniapp":
                result = client.prune_old(args.keep)
                print(f"pruned miniapp bundles: {result.get('deletedCount', 0)} deleted, {result.get('failedCount', 0)} failed")
                if result.get("failedCount"):
                    return 1
            else:
                removed = client.prune(args.kind, args.keep)
                print(f"pruned plugin bundles: {', '.join(removed) if removed else 'nothing to delete'}")
        else:
            client.deploy_component()
            print("component deployment started")
    except (ci_http.ApiError, miniapp_config.ConfigError, ValueError, OSError) as error:
        print(f"up_api: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
