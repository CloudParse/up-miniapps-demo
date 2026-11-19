import os
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / ".gitea" / "scripts"))

import bundle  # noqa: E402
import miniapp_config as mc  # noqa: E402


class BundleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cwd = os.getcwd()
        os.chdir(self.tmp.name)
        self.addCleanup(os.chdir, self.cwd)

    def test_miniapp_tarball_holds_the_content_of_out(self) -> None:
        out = Path("miniapp/dist/assets")
        out.mkdir(parents=True)
        Path("miniapp/dist/index.html").write_text("<html/>")
        (out / "a.js").write_text("1")
        config = {"miniapp": {"dir": "miniapp", "out": "dist"}}
        target = bundle.pack_miniapp(config, "1.2.3", Path("dist-ci"))
        self.assertEqual(target.name, "miniapp-1.2.3.tar.gz")
        with tarfile.open(target) as archive:
            self.assertEqual(sorted(archive.getnames()), ["assets", "assets/a.js", "index.html"])
            self.assertTrue(all(member.uid == 0 and member.mtime == 0 for member in archive.getmembers()))

    def test_empty_output_refused(self) -> None:
        Path("miniapp/dist").mkdir(parents=True)
        with self.assertRaisesRegex(mc.ConfigError, "produced nothing"):
            bundle.pack_miniapp({"miniapp": {"dir": "miniapp", "out": "dist"}}, "1.0.0", Path("o"))

    def test_symlink_refused(self) -> None:
        Path("miniapp/dist").mkdir(parents=True)
        os.symlink("/etc/passwd", "miniapp/dist/link")
        with self.assertRaisesRegex(mc.ConfigError, "symbolic link"):
            bundle.pack_miniapp({"miniapp": {"dir": "miniapp", "out": "dist"}}, "1.0.0", Path("o"))

    def test_plugin_is_one_module(self) -> None:
        Path("plugin/dist").mkdir(parents=True)
        Path("plugin/dist/plugin.mjs").write_text("export default {}")
        config = {"plugin": {"dir": "plugin", "out": "dist", "file": "plugin.mjs"}}
        target = bundle.pack_plugin(config, "1.2.3", Path("dist-ci"))
        self.assertEqual(target.name, "plugin-1.2.3.mjs")
        self.assertEqual(target.read_text(), "export default {}")

    def test_missing_plugin_build_refused(self) -> None:
        with self.assertRaisesRegex(mc.ConfigError, "did not produce"):
            bundle.pack_plugin({"plugin": {"dir": "p", "out": "dist", "file": "x.mjs"}}, "1.0.0", Path("o"))


if __name__ == "__main__":
    unittest.main()
