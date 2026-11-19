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

MINIAPP = {"miniapp": {"dir": "miniapp", "out": "dist"}}
PLUGIN = {"plugin": {"dir": "plugin", "out": "dist", "file": "plugin.mjs"}}


class BundleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.cwd = os.getcwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, self.cwd)

    def make_miniapp(self) -> None:
        (self.root / "miniapp/dist/assets").mkdir(parents=True)
        (self.root / "miniapp/dist/index.html").write_text("<html/>")
        (self.root / "miniapp/dist/assets/a.js").write_text("1")

    def test_miniapp_tarball_holds_the_content_of_out(self) -> None:
        self.make_miniapp()
        target = bundle.pack_miniapp(MINIAPP, "1.2.3", Path("dist-ci"))
        self.assertEqual(target.name, "miniapp-1.2.3.tar.gz")
        with tarfile.open(target) as archive:
            self.assertEqual(sorted(archive.getnames()), ["assets", "assets/a.js", "index.html"])
            self.assertTrue(all(m.uid == 0 and m.mtime == 0 for m in archive.getmembers()))

    def test_version_is_checked(self) -> None:
        self.make_miniapp()
        for bad in ("../x", "1.2", 'a".tar.gz', "1.2.3\n"):
            with self.subTest(bad), self.assertRaises(mc.ConfigError):
                bundle.pack_miniapp(MINIAPP, bad, Path("dist-ci"))

    def test_empty_output_refused(self) -> None:
        (self.root / "miniapp/dist").mkdir(parents=True)
        with self.assertRaisesRegex(mc.ConfigError, "produced nothing"):
            bundle.pack_miniapp(MINIAPP, "1.0.0", Path("dist-ci"))

    def test_symlink_inside_the_output_is_refused(self) -> None:
        self.make_miniapp()
        os.symlink("/etc/passwd", self.root / "miniapp/dist/link")
        with self.assertRaisesRegex(mc.ConfigError, "not a regular file"):
            bundle.pack_miniapp(MINIAPP, "1.0.0", Path("dist-ci"))

    def test_symlinked_dir_out_and_file_are_refused(self) -> None:
        outside = self.root.parent / (self.root.name + "-outside")
        outside.mkdir()
        self.addCleanup(outside.rmdir)
        (outside / "index.html").write_text("x")
        self.addCleanup((outside / "index.html").unlink)
        (self.root / "miniapp").symlink_to(outside)
        with self.assertRaisesRegex(mc.ConfigError, "symbolic link"):
            bundle.pack_miniapp({"miniapp": {"dir": "miniapp", "out": "."}}, "1.0.0", Path("dist-ci"))
        (self.root / "miniapp").unlink()
        (self.root / "miniapp").mkdir()
        (self.root / "miniapp" / "dist").symlink_to(outside)
        with self.assertRaisesRegex(mc.ConfigError, "symbolic link"):
            bundle.pack_miniapp(MINIAPP, "1.0.0", Path("dist-ci"))
        (self.root / "plugin/dist").mkdir(parents=True)
        (self.root / "plugin/dist/plugin.mjs").symlink_to(outside / "index.html")
        with self.assertRaisesRegex(mc.ConfigError, "symbolic link"):
            bundle.pack_plugin(PLUGIN, "1.0.0", Path("dist-ci"))

    def test_a_path_that_leaves_the_repository_is_refused(self) -> None:
        for section in ({"dir": "..", "out": "dist"}, {"dir": "a", "out": "../../x"}):
            with self.subTest(section), self.assertRaises(mc.ConfigError):
                bundle.pack_miniapp({"miniapp": section}, "1.0.0", Path("dist-ci"))

    def test_output_folder_must_not_overlap_the_sources_or_be_the_root(self) -> None:
        self.make_miniapp()
        for out in (Path("miniapp/dist"), Path("miniapp/dist/sub"), Path("miniapp"), Path("."), Path("/tmp/elsewhere")):
            with self.subTest(out), self.assertRaises(mc.ConfigError):
                bundle.pack_miniapp(MINIAPP, "1.0.0", out)

    def test_plugin_is_one_module(self) -> None:
        (self.root / "plugin/dist").mkdir(parents=True)
        (self.root / "plugin/dist/plugin.mjs").write_text("export default {}")
        target = bundle.pack_plugin(PLUGIN, "1.2.3", Path("dist-ci"))
        self.assertEqual(target.name, "plugin-1.2.3.mjs")
        self.assertEqual(target.read_text(), "export default {}")

    def test_missing_plugin_build_refused(self) -> None:
        with self.assertRaisesRegex(mc.ConfigError, "did not produce"):
            bundle.pack_plugin(PLUGIN, "1.0.0", Path("dist-ci"))


if __name__ == "__main__":
    unittest.main()
