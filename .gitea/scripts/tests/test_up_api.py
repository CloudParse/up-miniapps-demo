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
import miniapp_config  # noqa: E402
import up_api  # noqa: E402
from mock_server import MockServer  # noqa: E402

APP = "5b5101d1-0f4c-4b7e-9a35-2d6f1f0c7a11"


class LocalHttp(unittest.TestCase):
    """The mock server speaks plain http, which the scripts refuse unless a development cluster says otherwise."""

    def setUp(self) -> None:
        patcher = unittest.mock.patch.dict(os.environ, {"UP_CI_ALLOW_HTTP": "true"})
        patcher.start()
        self.addCleanup(patcher.stop)


import unittest.mock  # noqa: E402


def token_or(answer):
    def responder(method: str, path: str, headers: dict, body: bytes):
        return (200, {"token": "jwt-1", "expiresAt": 1800}) if path.endswith("/ci/token") else answer

    return responder


class UpApiTest(LocalHttp):
    def test_token_then_publish_miniapp_with_form_fields(self) -> None:
        with MockServer(token_or((201, {"uuid": "x"}))) as server, tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "miniapp-1.0.1.tar.gz"
            bundle.write_bytes(b"\x1f\x8bdata")
            up_api.Client(server.url + "/api/v1", APP, "cid", "secret").publish("miniapp", "1.0.1", bundle)
            token_call, publish = server.calls
            self.assertEqual(json.loads(token_call["body"]), {"clientId": "cid", "clientSecret": "secret"})
            self.assertEqual(publish["path"], f"/api/v1/admin/applications/{APP}/artifacts")
            self.assertEqual(publish["headers"]["authorization"], "Bearer jwt-1")
            self.assertIn(b'name="version"\r\n\r\n1.0.1', publish["body"])
            self.assertNotIn(b'name="changelog"', publish["body"])
            self.assertIn(b'filename="miniapp-1.0.1.tar.gz"', publish["body"])

    def test_publish_plugin_activates(self) -> None:
        with MockServer(token_or((201, {}))) as server, tempfile.TemporaryDirectory() as tmp:
            module = Path(tmp) / "plugin-1.0.1.mjs"
            module.write_text("export default {}")
            up_api.Client(server.url, APP, "c", "s").publish("plugin", "1.0.1", module)
            publish = server.calls[-1]
            self.assertEqual(publish["path"], f"/admin/applications/{APP}/backoffice-plugin/artifacts")
            self.assertIn(b'name="activate"\r\n\r\ntrue', publish["body"])

    def test_deploy_sends_the_tag_and_nothing_else(self) -> None:
        with MockServer(token_or((202, {}))) as server:
            up_api.Client(server.url, APP, "c", "s").deploy_component("1.4.2")
            call = server.calls[-1]
            self.assertEqual(call["path"], f"/admin/applications/{APP}/custom-component/deploy")
            self.assertEqual(json.loads(call["body"]), {"tag": "1.4.2"})

    def test_a_bad_version_never_reaches_the_server(self) -> None:
        with MockServer(token_or((201, {}))) as server, tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "b.tar.gz"
            bundle.write_bytes(b"x")
            client = up_api.Client(server.url, APP, "c", "s")
            for bad in ('1.0.0"; filename="x', "1.0.0\r\nX: y", "../1.0.0", "1.0", "latest", "1.0.0\n"):
                with self.subTest(bad):
                    with self.assertRaises(miniapp_config.ConfigError):
                        client.publish("miniapp", bad, bundle)
                    with self.assertRaises(miniapp_config.ConfigError):
                        client.deploy_component(bad)
            self.assertEqual(server.calls, [])

    def test_multipart_refuses_injection_in_names_and_values(self) -> None:
        for filename in ('a"; name="version', "a\r\nb", "../a", "a b", ""):
            with self.subTest(filename), self.assertRaises(ci_http.ApiError):
                ci_http.multipart({"version": "1.0.0"}, "file", filename, b"x")
        with self.assertRaises(ci_http.ApiError):
            ci_http.multipart({"version": "1.0.0\r\n--x"}, "file", "a.bin", b"x")
        with self.assertRaises(ci_http.ApiError):
            ci_http.multipart({'ver"sion': "1"}, "file", "a.bin", b"x")

    def test_deploy_error_message_is_cut_and_cleaned(self) -> None:
        long = "tag not in the registry\x1b[31m" + "A" * 1000
        with MockServer(token_or((409, {"message": long}))) as server:
            with self.assertRaises(ci_http.ApiError) as raised:
                up_api.Client(server.url, APP, "c", "s").deploy_component("1.0.0")
            self.assertEqual(raised.exception.status, 409)
            self.assertNotIn("\x1b", str(raised.exception))
            self.assertLess(len(str(raised.exception)), 260)

    def test_token_refused(self) -> None:
        with MockServer(lambda *a: (401, {"message": "invalid client"})) as server:
            with self.assertRaisesRegex(ci_http.ApiError, "invalid client"):
                up_api.Client(server.url, APP, "c", "bad").token()

    def test_redirects_are_never_followed(self) -> None:
        def responder(method: str, path: str, headers: dict, body: bytes):
            if path == "/elsewhere":
                return 200, {"token": "stolen"}
            return 302, None, {"Location": "/elsewhere"}

        with MockServer(responder) as server:
            with self.assertRaisesRegex(ci_http.ApiError, "redirect"):
                up_api.Client(server.url, APP, "c", "s").token()
            self.assertEqual([c["path"] for c in server.calls], ["/ci/token"])

    def test_non_json_answer_is_an_error(self) -> None:
        def responder(method: str, path: str, headers: dict, body: bytes):
            return 200, "not an object"

        with MockServer(responder) as server:
            with self.assertRaises(ci_http.ApiError):
                up_api.Client(server.url, APP, "c", "s").token()

    def test_unreachable_server_and_missing_env(self) -> None:
        with self.assertRaisesRegex(ci_http.ApiError, "cannot reach"):
            up_api.Client("http://127.0.0.1:9", APP, "c", "s").token()
        with unittest.mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("UP_API_URL", None)
            with self.assertRaisesRegex(ci_http.ApiError, "UP_API_URL is not set"):
                up_api.Client.from_env(APP)

    def test_the_client_only_offers_publish_and_deploy(self) -> None:
        names = {name for name in dir(up_api.Client) if not name.startswith("_")}
        self.assertEqual(names, {"from_env", "token", "publish", "deploy_component"})


class HttpsOnlyTest(unittest.TestCase):
    def test_http_is_refused_by_default_and_allowed_by_the_flag(self) -> None:
        with unittest.mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("UP_CI_ALLOW_HTTP", None)
            for url in ("http://api.example/api/v1", "ftp://x", "//x", "file:///etc/passwd"):
                with self.subTest(url), self.assertRaises(ci_http.ApiError):
                    ci_http.check_url(url)
            with self.assertRaises(ci_http.ApiError):
                up_api.Client("http://api.example/api/v1", APP, "c", "s")
            ci_http.check_url("https://api.example/api/v1")
        with unittest.mock.patch.dict(os.environ, {"UP_CI_ALLOW_HTTP": "true"}):
            ci_http.check_url("http://127.0.0.1:1")
            with self.assertRaises(ci_http.ApiError):
                ci_http.check_url("ftp://x")


if __name__ == "__main__":
    unittest.main()
