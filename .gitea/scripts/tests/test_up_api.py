import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / ".gitea" / "scripts"))
sys.path.insert(0, str(Path(__file__).parent))

import ci_http  # noqa: E402
import up_api  # noqa: E402
from mock_server import MockServer  # noqa: E402

APP = "5b5101d1-0f4c-4b7e-9a35-2d6f1f0c7a11"


def artifacts(*versions: str) -> list[dict]:
    return [
        {"uuid": f"u-{version}", "version": version, "createdAt": f"2026-11-0{index + 1}T10:00:00Z"}
        for index, version in enumerate(versions)
    ]


class UpApiTest(unittest.TestCase):
    def test_token_then_publish_miniapp_with_form_fields(self) -> None:
        def responder(method: str, path: str, headers: dict, body: bytes):
            if path.endswith("/ci/token"):
                return 200, {"token": "jwt-1", "expiresAt": 300}
            return 201, {"uuid": "x"}

        with MockServer(responder) as server, tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "miniapp-1.0.1.tar.gz"
            bundle.write_bytes(b"\x1f\x8bdata")
            client = up_api.Client(server.url + "/api/v1", APP, "cid", "secret")
            client.publish("miniapp", "1.0.1", bundle)
            token_call, publish = server.calls
            self.assertEqual(json.loads(token_call["body"]), {"clientId": "cid", "clientSecret": "secret"})
            self.assertEqual(publish["path"], f"/api/v1/admin/applications/{APP}/artifacts")
            self.assertEqual(publish["headers"]["authorization"], "Bearer jwt-1")
            self.assertIn(b'name="version"\r\n\r\n1.0.1', publish["body"])
            self.assertNotIn(b'name="changelog"', publish["body"])
            self.assertIn(b'filename="miniapp-1.0.1.tar.gz"', publish["body"])

    def test_publish_plugin_activates(self) -> None:
        with MockServer(lambda *a: (200, {"token": "t"}) if a[1].endswith("/ci/token") else (201, {})) as server:
            with tempfile.TemporaryDirectory() as tmp:
                module = Path(tmp) / "plugin-1.0.1.mjs"
                module.write_text("export default {}")
                up_api.Client(server.url, APP, "c", "s").publish("plugin", "1.0.1", module)
            publish = server.calls[-1]
            self.assertEqual(publish["path"], f"/admin/applications/{APP}/backoffice-plugin/artifacts")
            self.assertIn(b'name="activate"\r\n\r\ntrue', publish["body"])

    def test_prune_miniapp_uses_the_prune_old_route(self) -> None:
        def responder(method: str, path: str, headers: dict, body: bytes):
            if path.endswith("/ci/token"):
                return 200, {"token": "t"}
            return 200, {"deletedCount": 2, "failedCount": 0}

        with MockServer(responder) as server:
            result = up_api.Client(server.url, APP, "c", "s").prune_old(5)
            self.assertEqual(result["deletedCount"], 2)
            call = server.calls[-1]
            self.assertEqual((call["method"], call["path"]), ("DELETE", "/admin/applications/artifacts/prune-old?keep=5"))
            with self.assertRaises(ValueError):
                up_api.Client(server.url, APP, "c", "s").prune_old(3)

    def test_prune_follows_pages_and_keeps_the_newest(self) -> None:
        pages = {"": (artifacts("1.0.1", "1.0.2", "1.0.3"), "c2"), "c2": ([{"uuid": "u-1.0.9", "version": "1.0.9", "createdAt": "2026-11-09T10:00:00Z"}], "c3")}

        def responder(method: str, path: str, headers: dict, body: bytes):
            if path.endswith("/ci/token"):
                return 200, {"token": "t"}
            if method == "GET":
                cursor = path.split("cursor=")[1] if "cursor=" in path else ""
                data, nxt = pages.get(cursor, ([], None))
                return 200, {"data": data, "nextCursor": nxt}
            return 204, None

        with MockServer(responder) as server:
            removed = up_api.Client(server.url, APP, "c", "s").prune("plugin", 3)
            self.assertEqual(removed, ["1.0.1"])
            self.assertEqual(
                [c["path"] for c in server.calls if c["method"] == "DELETE"],
                ["/admin/backoffice-plugins/artifacts/u-1.0.1"],
            )

    def test_prune_plugin_uses_plugin_routes(self) -> None:
        def responder(method: str, path: str, headers: dict, body: bytes):
            if path.endswith("/ci/token"):
                return 200, {"token": "t"}
            if method == "GET":
                return 200, {"data": artifacts("1.0.1", "1.0.2", "1.0.3", "1.0.4"), "nextCursor": None}
            return 204, None

        with MockServer(responder) as server:
            up_api.Client(server.url, APP, "c", "s").prune("plugin", 3)
            self.assertEqual(
                [c["path"] for c in server.calls if c["method"] == "DELETE"],
                ["/admin/backoffice-plugins/artifacts/u-1.0.1"],
            )

    def test_deploy_component_and_error_message(self) -> None:
        def responder(method: str, path: str, headers: dict, body: bytes):
            if path.endswith("/ci/token"):
                return 200, {"token": "t"}
            return 409, {"message": "a deployment is already running"}

        with MockServer(responder) as server:
            client = up_api.Client(server.url, APP, "c", "s")
            with self.assertRaisesRegex(ci_http.ApiError, "already running") as raised:
                client.deploy_component()
            self.assertEqual(raised.exception.status, 409)
            self.assertEqual(server.calls[-1]["path"], f"/admin/applications/{APP}/custom-component/deploy")

    def test_token_refused(self) -> None:
        with MockServer(lambda *a: (401, {"message": "invalid client"})) as server:
            with self.assertRaisesRegex(ci_http.ApiError, "invalid client"):
                up_api.Client(server.url, APP, "c", "bad").token()

    def test_unreachable_server_and_missing_env(self) -> None:
        with self.assertRaisesRegex(ci_http.ApiError, "cannot reach"):
            up_api.Client("http://127.0.0.1:9", APP, "c", "s").token()
        old = os.environ.pop("UP_API_URL", None)
        try:
            with self.assertRaisesRegex(ci_http.ApiError, "UP_API_URL is not set"):
                up_api.Client.from_env(APP)
        finally:
            if old is not None:
                os.environ["UP_API_URL"] = old

    def test_prune_refuses_keep_below_one(self) -> None:
        with self.assertRaises(ValueError):
            up_api.Client("http://x", APP, "c", "s").prune("miniapp", 0)


if __name__ == "__main__":
    unittest.main()
