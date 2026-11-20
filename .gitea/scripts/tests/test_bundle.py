import base64
import gzip
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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

    def make_miniapp(self, html: str = "<html><body>é</body></html>") -> bytes:
        """What `up-sdk build` writes: dist/index.html and dist/index.base64.gz = gzip(base64(html))."""
        (self.root / "miniapp/dist").mkdir(parents=True)
        (self.root / "miniapp/dist/index.html").write_text(html)
        packed = gzip.compress(base64.b64encode(html.encode("utf-8")))
        (self.root / "miniapp/dist/index.base64.gz").write_bytes(packed)
        return packed

    def write_miniapp_file(self, data: bytes) -> None:
        (self.root / "miniapp/dist").mkdir(parents=True, exist_ok=True)
        (self.root / "miniapp/dist/index.base64.gz").write_bytes(data)

    def test_miniapp_file_is_copied_as_it_is(self) -> None:
        packed = self.make_miniapp()
        target = bundle.pack_miniapp(MINIAPP, "1.2.3", Path("dist-ci"))
        self.assertEqual(target.name, "miniapp-1.2.3.base64.gz")
        self.assertEqual(target.read_bytes(), packed, "the platform checksum is the one of the file the SDK wrote")

    def test_a_real_up_sdk_output_with_wrapped_base64_is_accepted(self) -> None:
        html = "<html>" + "x" * 500 + "</html>"
        wrapped = base64.encodebytes(html.encode())  # lines of 76 characters, like the base64 tool
        self.write_miniapp_file(gzip.compress(wrapped))
        self.assertTrue(bundle.pack_miniapp(MINIAPP, "1.0.0", Path("dist-ci")).exists())

    def test_a_missing_file_says_to_run_up_sdk_build(self) -> None:
        (self.root / "miniapp/dist").mkdir(parents=True)
        (self.root / "miniapp/dist/index.html").write_text("<html/>")
        with self.assertRaisesRegex(mc.ConfigError, r"did not write index\.base64\.gz.*up-sdk build"):
            bundle.pack_miniapp(MINIAPP, "1.0.0", Path("dist-ci"))

    def test_a_file_that_is_not_what_the_launcher_reads_is_refused(self) -> None:
        cases = {
            "not gzip": (b"<html/>", "not a gzip file"),
            "a tar.gz of the folder": (gzip.compress(b"index.html\x00" + b"0" * 600), "base64"),
            "gzip of raw html": (gzip.compress(b"<html><body>hello world</body></html>"), "base64"),
            "base64 of bytes that are not UTF-8": (gzip.compress(base64.b64encode(b"\xff\xfe\xfd")), "UTF-8"),
            "empty page": (gzip.compress(base64.b64encode(b"   ")), "empty page"),
            "truncated gzip": (gzip.compress(base64.b64encode(b"<html>" + b"a" * 2000 + b"</html>"))[:-12], "truncated"),
            "data after the stream": (gzip.compress(base64.b64encode(b"<html/>")) + b"junk", "after the gzip stream"),
            "bad gzip body": (b"\x1f\x8b" + b"\x00" * 20, "valid gzip"),
        }
        for name, (data, message) in cases.items():
            with self.subTest(name):
                self.write_miniapp_file(data)
                with self.assertRaisesRegex(mc.ConfigError, message):
                    bundle.pack_miniapp(MINIAPP, "1.0.0", Path("dist-ci"))
                self.assertFalse(list((self.root / "dist-ci").glob("miniapp-*")), "nothing is written when the file is refused")

    def test_version_is_checked(self) -> None:
        self.make_miniapp()
        for bad in ("../x", "1.2", 'a".base64.gz', "1.2.3\n"):
            with self.subTest(bad), self.assertRaises(mc.ConfigError):
                bundle.pack_miniapp(MINIAPP, bad, Path("dist-ci"))

    def test_empty_output_refused(self) -> None:
        (self.root / "miniapp/dist").mkdir(parents=True)
        with self.assertRaisesRegex(mc.ConfigError, "did not write"):
            bundle.pack_miniapp(MINIAPP, "1.0.0", Path("dist-ci"))
        self.write_miniapp_file(b"")
        with self.assertRaisesRegex(mc.ConfigError, "empty"):
            bundle.pack_miniapp(MINIAPP, "1.0.0", Path("dist-ci"))

    def test_a_symlinked_miniapp_file_is_refused(self) -> None:
        packed = self.make_miniapp()
        (self.root / "miniapp/dist/index.base64.gz").unlink()
        real = self.root / "real.gz"
        real.write_bytes(packed)
        os.symlink(real, self.root / "miniapp/dist/index.base64.gz")
        with self.assertRaisesRegex(mc.ConfigError, "symbolic link"):
            bundle.pack_miniapp(MINIAPP, "1.0.0", Path("dist-ci"))

    def test_symlinked_dir_out_and_file_are_refused(self) -> None:
        outside = self.root.parent / (self.root.name + "-outside")
        outside.mkdir()
        self.addCleanup(outside.rmdir)
        (outside / "index.html").write_text("x")
        self.addCleanup((outside / "index.html").unlink)
        (outside / "index.base64.gz").write_bytes(gzip.compress(base64.b64encode(b"<html/>")))
        self.addCleanup((outside / "index.base64.gz").unlink)
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

    def test_a_hard_link_in_the_output_is_refused(self) -> None:
        self.make_miniapp()
        os.link(self.root / "miniapp/dist/index.base64.gz", self.root / "miniapp/dist/copy.gz")
        with self.assertRaisesRegex(mc.ConfigError, "hard link"):
            bundle.pack_miniapp(MINIAPP, "1.0.0", Path("dist-ci"))

    def test_the_sizes_are_capped(self) -> None:
        self.make_miniapp()
        with mock.patch.object(bundle, "MAX_COMPRESSED_BYTES", 5):
            with self.assertRaisesRegex(mc.ConfigError, "MB"):
                bundle.pack_miniapp(MINIAPP, "1.0.0", Path("dist-ci"))
        with mock.patch.object(bundle, "MAX_HTML_BYTES", 8):
            with self.assertRaisesRegex(mc.ConfigError, "more than 0 MB of HTML"):
                bundle.pack_miniapp(MINIAPP, "1.0.0", Path("dist-ci"))
        self.assertFalse(list((self.root / "dist-ci").glob("miniapp-*")), "nothing is written when a limit is hit")

    def test_a_gzip_bomb_is_stopped_while_inflating(self) -> None:
        self.write_miniapp_file(gzip.compress(b"A" * (3 * 1024 * 1024)))
        with mock.patch.object(bundle, "MAX_HTML_BYTES", 1024):
            with self.assertRaisesRegex(mc.ConfigError, "of HTML"):
                bundle.pack_miniapp(MINIAPP, "1.0.0", Path("dist-ci"))

    def test_the_plugin_size_is_capped_and_hard_links_are_refused(self) -> None:
        (self.root / "plugin/dist").mkdir(parents=True)
        (self.root / "plugin/dist/plugin.mjs").write_text("export default {}")
        with mock.patch.object(bundle, "MAX_PLUGIN_BYTES", 3):
            with self.assertRaisesRegex(mc.ConfigError, "MB"):
                bundle.pack_plugin(PLUGIN, "1.0.0", Path("dist-ci"))
        os.link(self.root / "plugin/dist/plugin.mjs", self.root / "plugin/dist/other.mjs")
        with self.assertRaisesRegex(mc.ConfigError, "hard link"):
            bundle.pack_plugin(PLUGIN, "1.0.0", Path("dist-ci"))

    def test_a_target_that_is_a_symbolic_link_is_never_written_through(self) -> None:
        self.make_miniapp()
        victim = self.root / "victim.txt"
        victim.write_text("keep")
        (self.root / "dist-ci").mkdir()
        (self.root / "dist-ci" / "miniapp-1.0.0.base64.gz").symlink_to(victim)
        with self.assertRaisesRegex(mc.ConfigError, "symbolic link"):
            bundle.pack_miniapp(MINIAPP, "1.0.0", Path("dist-ci"))
        self.assertEqual(victim.read_text(), "keep")
        (self.root / "plugin/dist").mkdir(parents=True)
        (self.root / "plugin/dist/plugin.mjs").write_text("x")
        (self.root / "dist-ci" / "plugin-1.0.0.mjs").symlink_to(victim)
        with self.assertRaisesRegex(mc.ConfigError, "symbolic link"):
            bundle.pack_plugin(PLUGIN, "1.0.0", Path("dist-ci"))
        self.assertEqual(victim.read_text(), "keep")

    def test_an_existing_regular_target_is_replaced(self) -> None:
        packed = self.make_miniapp()
        bundle.pack_miniapp(MINIAPP, "1.0.0", Path("dist-ci"))
        target = bundle.pack_miniapp(MINIAPP, "1.0.0", Path("dist-ci"))
        self.assertEqual(target.read_bytes(), packed)


if __name__ == "__main__":
    unittest.main()
