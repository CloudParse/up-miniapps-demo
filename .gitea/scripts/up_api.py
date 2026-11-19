"""Calls of the deployment CI to the organisation API, authenticated with the credentials of the mini-app.

Environment (Gitea Actions secrets, never arguments):
  UP_API_URL         base of the organisation API including /api/v1, e.g. https://api.<slug>.<domain>/api/v1
  UP_CLIENT_ID       client id of the mini-app
  UP_CLIENT_SECRET   client secret of the mini-app
The mini-app uuid comes from miniapp.yaml.

Usage: up_api.py publish miniapp|plugin --version 1.2.3 --file <path>
       up_api.py deploy-component --version 1.2.3   (the image <registry>/<owner>/<repo>:1.2.3 is already pushed)
The CI token may only publish bundles and plugin versions and roll out the component: nothing here deletes. Retention is the
server's (the organisation API keeps the newest 5 versions after each publish).
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Any

import ci_http
import miniapp_config

KINDS = ("miniapp", "plugin")


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ci_http.ApiError(0, f"{name} is not set: the platform writes it as an Actions secret of this repository")
    return value


class Client:
    def __init__(self, api_url: str, app_uuid: str, client_id: str, client_secret: str) -> None:
        ci_http.check_url(api_url)
        self.api = api_url.rstrip("/")
        miniapp_config.check_uuid(app_uuid)
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

    def _publish_url(self, kind: str) -> str:
        if kind == "miniapp":
            return f"{self.api}/admin/applications/{self.app_uuid}/artifacts"
        return f"{self.api}/admin/applications/{self.app_uuid}/backoffice-plugin/artifacts"

    def publish(self, kind: str, version: str, file_path: Path) -> Any:
        """Upload one bundle with an empty changelog; the plugin becomes the active one."""
        miniapp_config.check_version(version)
        fields = {"version": version}
        if kind == "plugin":
            fields["activate"] = "true"
        body, content_type = ci_http.multipart(fields, "file", file_path.name, file_path.read_bytes())
        headers = {"Authorization": f"Bearer {self.token()}", "Content-Type": content_type, "Accept": "application/json"}
        return ci_http.request("POST", self._publish_url(kind), headers=headers, body=body)

    def deploy_component(self, version: str) -> Any:
        """Ask the platform to deploy the pushed image: it sets the tag to `version` only when the registry holds it."""
        miniapp_config.check_version(version)
        url = f"{self.api}/admin/applications/{self.app_uuid}/custom-component/deploy"
        return ci_http.request_json("POST", url, {"tag": version}, token=self.token())


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="miniapp.yaml")
    sub = parser.add_subparsers(dest="command", required=True)
    publish = sub.add_parser("publish")
    publish.add_argument("kind", choices=KINDS)
    publish.add_argument("--version", required=True)
    publish.add_argument("--file", required=True, type=Path)
    deploy = sub.add_parser("deploy-component")
    deploy.add_argument("--version", required=True)
    args = parser.parse_args(argv)
    try:
        config = miniapp_config.load(Path(args.config))
        miniapp_config.validate(config)
        client = Client.from_env(str(config["uuid"]))
        if args.command == "publish":
            client.publish(args.kind, args.version, args.file)
            print(f"published {args.kind} {args.version}")
        else:
            client.deploy_component(args.version)
            print(f"deployment of {args.version} started")
    except (ci_http.ApiError, miniapp_config.ConfigError, OSError) as error:
        print(f"up_api: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
