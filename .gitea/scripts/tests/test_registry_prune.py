import base64
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / ".gitea" / "scripts"))
sys.path.insert(0, str(Path(__file__).parent))

import registry_prune  # noqa: E402
from mock_server import MockServer  # noqa: E402


class RegistryPruneTest(unittest.TestCase):
    def test_keeps_only_current_version_and_ignores_other_packages(self) -> None:
        listing = [
            {"name": "demo-atlas-5b51", "version": "1.0.3"},
            {"name": "demo-atlas-5b51", "version": "1.0.2"},
            {"name": "demo-atlas-5b51-extra", "version": "9.9.9"},
            {"name": "demo-atlas-5b51", "version": "1.0.1"},
        ]

        def responder(method: str, path: str, headers: dict, body: bytes):
            return (200, listing) if method == "GET" else (204, None)

        auth = base64.b64encode(b"ci:tok").decode()
        with MockServer(responder) as server:
            removed = registry_prune.prune(server.url, "demo", "demo-atlas-5b51", "1.0.3", auth)
            self.assertEqual(removed, ["1.0.2", "1.0.1"])
            deletes = [c["path"] for c in server.calls if c["method"] == "DELETE"]
            self.assertEqual(
                deletes,
                ["/api/v1/packages/demo/container/demo-atlas-5b51/1.0.2", "/api/v1/packages/demo/container/demo-atlas-5b51/1.0.1"],
            )
            self.assertEqual(server.calls[0]["headers"]["authorization"], f"Basic {auth}")
            self.assertIn("type=container", server.calls[0]["path"])


if __name__ == "__main__":
    unittest.main()
