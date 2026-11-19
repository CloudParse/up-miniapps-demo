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

    def test_the_client_has_no_delete_or_prune_call(self) -> None:
        names = {name for name in dir(up_api.Client) if not name.startswith("__")}
        self.assertFalse({"prune", "prune_old", "delete"} & names)
        self.assertNotIn("DELETE", Path(up_api.__file__).read_text())

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


if __name__ == "__main__":
    unittest.main()
