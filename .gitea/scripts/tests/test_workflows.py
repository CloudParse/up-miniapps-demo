"""Runs the shell steps of the deploy workflows against a mock platform, as the runner would (checkout excluded)."""

import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).parent))

from mock_server import MockServer  # noqa: E402

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

APP = "5b5101d1-0f4c-4b7e-9a35-2d6f1f0c7a11"
CONFIG = f"""version: 2
uuid: {APP}
slug: atlas
name: Atlas
api:
  dir: api
  port: 8000
miniapp:
  dir: miniapp
  build: mkdir -p dist && echo hello > dist/index.html
  out: dist
plugin:
  dir: plugin
  build: mkdir -p dist && echo 'export default {{}}' > dist/plugin.mjs
  out: dist
  file: plugin.mjs
"""


def load(name: str) -> dict:
    return yaml.safe_load((ROOT / ".gitea" / "workflows" / name).read_text())


def steps(workflow: dict) -> list[dict]:
    return next(iter(workflow["jobs"].values()))["steps"]


def expand(value: str, context: dict[str, str]) -> str:
    return re.sub(r"\$\{\{\s*([\w.]+)\s*\}\}", lambda m: context[m.group(1)], value)


@unittest.skipIf(yaml is None, "PyYAML missing")
class WorkflowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.src = Path(self.tmp.name) / "src"
        shutil.copytree(ROOT / ".gitea", self.src / ".gitea", ignore=shutil.ignore_patterns("tests", "__pycache__"))
        (self.src / "miniapp.yaml").write_text(CONFIG)
        (self.src / "miniapp").mkdir()
        (self.src / "plugin").mkdir()

    def run_steps(self, name: str, context: dict[str, str], skip: tuple[str, ...] = ("Check out the repository",)) -> None:
        for step in steps(load(name)):
            if step["name"] in skip:
                continue
            env = {**os.environ, **{k: expand(v, context) for k, v in step.get("env", {}).items()}}
            result = subprocess.run(  # noqa: S603
                ["bash", "-c", expand(step["run"], context)], cwd=self.src, env=env, capture_output=True, text=True
            )
            self.assertEqual(result.returncode, 0, f"{step['name']}\n{result.stdout}\n{result.stderr}")
            self.assertNotIn("topsecret", result.stdout + result.stderr, f"secret printed in {step['name']}")

    def test_frontend_publishes_both_bundles_and_prunes(self) -> None:
        def responder(method: str, path: str, headers: dict, body: bytes):
            if path.endswith("/ci/token"):
                return 200, {"token": "jwt"}
            if method == "GET":
                return 200, {"data": [], "nextCursor": None}
            return 201, {}

        with MockServer(responder) as server:
            context = {
                "inputs.version": "1.0.4",
                "secrets.UP_API_URL": server.url,
                "secrets.UP_CLIENT_ID": "cid",
                "secrets.UP_CLIENT_SECRET": "topsecret",
            }
            self.run_steps("deploy-frontend.yml", context)
        posts = [c for c in server.calls if c["method"] == "POST" and "/admin/" in c["path"]]
        self.assertEqual(
            [p["path"] for p in posts],
            [f"/admin/applications/{APP}/artifacts", f"/admin/applications/{APP}/backoffice-plugin/artifacts"],
        )
        with tarfile.open(self.src / "dist-ci" / "miniapp-1.0.4.tar.gz") as archive:
            self.assertEqual(archive.getnames(), ["index.html"])
        self.assertTrue((self.src / "dist-ci" / "plugin-1.0.4.mjs").exists())

    def test_frontend_stops_on_invalid_config(self) -> None:
        (self.src / "miniapp.yaml").write_text(CONFIG.replace("version: 2", "version: 1"))
        with self.assertRaises(AssertionError) as raised:
            self.run_steps("deploy-frontend.yml", {"inputs.version": "1.0.4"})
        self.assertIn("Validate miniapp.yaml", str(raised.exception))
        self.assertIn("version: 2", str(raised.exception))

    def test_backend_builds_rolls_out_then_prunes_the_registry(self) -> None:
        (self.src / "api").mkdir()
        (self.src / "api" / "Dockerfile").write_text("FROM scratch\n")
        fake = Path(self.tmp.name) / "kaniko"
        args_file = Path(self.tmp.name) / "args"
        fake.write_text(f'#!/bin/sh\nprintf "%s\\n" "$@" > {args_file}\n')
        fake.chmod(0o755)

        def responder(method: str, path: str, headers: dict, body: bytes):
            if path.endswith("/ci/token"):
                return 200, {"token": "jwt"}
            if path.startswith("/api/v1/packages") and method == "GET":
                return 200, [{"name": "demo-atlas-5b51", "version": "1.0.3"}, {"name": "demo-atlas-5b51", "version": "1.0.2"}]
            return 200, {}

        os.environ["KANIKO_EXECUTOR"] = str(fake)
        self.addCleanup(os.environ.pop, "KANIKO_EXECUTOR", None)
        with MockServer(responder) as server:
            context = {
                "inputs.version": "1.0.3",
                "secrets.UP_API_URL": server.url,
                "secrets.UP_CLIENT_ID": "cid",
                "secrets.UP_CLIENT_SECRET": "topsecret",
                "secrets.REGISTRY_USER": "ci",
                "secrets.REGISTRY_TOKEN": "topsecret",
                "gitea.server_url": server.url,
                "gitea.repository": "demo/Demo-Atlas-5b51",
                "gitea.repository_owner": "demo",
            }
            self.run_steps("deploy-backend.yml", context)
        host = server.url.split("://")[1]
        self.assertIn(f"{host}/demo/demo-atlas-5b51:1.0.3", args_file.read_text().split())
        self.assertIn("--insecure", args_file.read_text().split())
        paths = [(c["method"], c["path"]) for c in server.calls]
        self.assertIn(("POST", f"/admin/applications/{APP}/custom-component/deploy"), paths)
        self.assertIn(("DELETE", "/api/v1/packages/demo/container/demo-atlas-5b51/1.0.2"), paths)
        self.assertNotIn(("DELETE", "/api/v1/packages/demo/container/demo-atlas-5b51/1.0.3"), paths)
        deploy_index = paths.index(("POST", f"/admin/applications/{APP}/custom-component/deploy"))
        delete_index = paths.index(("DELETE", "/api/v1/packages/demo/container/demo-atlas-5b51/1.0.2"))
        self.assertLess(deploy_index, delete_index)

    def test_workflows_declare_dispatch_runner_and_no_secret_in_build(self) -> None:
        for name in ("deploy-backend.yml", "deploy-frontend.yml"):
            workflow = load(name)
            triggers = workflow.get("on", workflow.get(True))
            self.assertIn("version", triggers["workflow_dispatch"]["inputs"])
            self.assertEqual(next(iter(workflow["jobs"].values()))["runs-on"], "up-ci")
        for step in steps(load("deploy-frontend.yml")):
            if step["name"].startswith("Build"):
                self.assertFalse(any("secrets." in str(v) for v in step.get("env", {}).values()))
        _ = json


if __name__ == "__main__":
    unittest.main()
