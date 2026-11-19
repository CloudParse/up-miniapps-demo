import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / ".gitea" / "scripts"))

import miniapp_config as mc  # noqa: E402

BASE = """version: 2
uuid: 5b5101d1-0f4c-4b7e-9a35-2d6f1f0c7a11
slug: atlas
name: Atlas
"""


def check(extra: str) -> None:
    mc.validate(mc.parse(BASE + extra))


class ParseTest(unittest.TestCase):
    def test_platform_written_file(self) -> None:
        text = (
            "# comment\nversion: 1\nuuid: 5b5101d1-0f4c-4b7e-9a35-2d6f1f0c7a11\nslug: atlas\nname: \"Atlas #1\"  # x\n"
            "description: ''\nlogo: null\ncardStyle: navy\ndarkTheme: null\ndeviceTypes: [PHONE, TABLET]  # a | b\n"
        )
        config = mc.parse(text)
        self.assertEqual(config["name"], "Atlas #1")
        self.assertEqual(config["deviceTypes"], ["PHONE", "TABLET"])
        self.assertIsNone(config["logo"])
        mc.validate(config)

    def test_block_list_and_nesting(self) -> None:
        config = mc.parse("api:\n  command:\n    - python\n    - -m\n  port: 8000\n")
        self.assertEqual(config["api"], {"command": ["python", "-m"], "port": 8000})

    def test_refuses_tabs_duplicates_and_anchors(self) -> None:
        for bad in ("a:\tb\n", "a: 1\na: 2\n", "a: &x 1\n", "a: |\n  text\n", "a: [1, 2\n"):
            with self.assertRaises(mc.ConfigError, msg=bad):
                mc.parse(bad)

    def test_example_in_docs_is_valid(self) -> None:
        config = mc.load(ROOT / "docs" / "miniapp.example.yaml")
        mc.validate(config)
        self.assertEqual(mc.plan(config, "backend"), "run")
        self.assertEqual(mc.plan(config, "frontend"), "run")
        self.assertTrue(mc.plan(config, "plugin").startswith("skip "))  # the example's plugin section is commented out


class ValidateTest(unittest.TestCase):
    def test_v1_is_valid_and_every_target_is_skipped(self) -> None:
        config = mc.parse(BASE.replace("version: 2", "version: 1"))
        mc.validate(config)
        for target in mc.TARGETS:
            self.assertTrue(mc.plan(config, target).startswith("skip "))

    def test_v1_with_deploy_sections_refused(self) -> None:
        with self.assertRaisesRegex(mc.ConfigError, "api: needs `version: 2`"):
            mc.validate(mc.parse(BASE.replace("version: 2", "version: 1") + "api:\n  dir: api\n  port: 80\n"))

    def test_plan_is_per_section_and_never_an_error_when_absent(self) -> None:
        config = mc.parse(BASE + "api:\n  dir: api\n  port: 8000\nplugin:\n  dir: p\n  build: b\n  out: dist\n  file: a.mjs\n")
        self.assertEqual(mc.plan(config, "backend"), "run")
        self.assertEqual(mc.plan(config, "plugin"), "run")
        self.assertRegex(mc.plan(config, "frontend"), r"^skip .*`miniapp` section")
        with self.assertRaises(mc.ConfigError):
            mc.plan(config, "nope")

    def test_plan_still_refuses_an_invalid_file(self) -> None:
        with self.assertRaises(mc.ConfigError):
            mc.plan(mc.parse(BASE + "api:\n  dir: api\n  port: 0\n"), "frontend")

    def test_rejects_bad_values(self) -> None:
        cases = {
            "api.port": "api:\n  dir: api\n  port: 70000\n",
            "api.dir": "api:\n  dir: ../api\n  port: 80\n",
            "api.healthPath": "api:\n  dir: api\n  port: 80\n  healthPath: healthz\n",
            "unknown key": "api:\n  dir: api\n  port: 80\n  extra: 1\n",
            "services": "services:\n  postgres: true\n",
            "services.cache": "api:\n  dir: api\n  port: 80\nservices:\n  cache: yes please\n",
            "plugin.file": "plugin:\n  dir: p\n  build: b\n  out: dist\n  file: plugin.tar.gz\n",
            "miniapp.out": "miniapp:\n  dir: m\n  build: b\n  out: /abs\n",
            "publicIngress": "api:\n  dir: api\n  port: 80\n  publicIngress: 1\n",
        }
        for name, extra in cases.items():
            with self.subTest(name), self.assertRaises(mc.ConfigError):
                check(extra)

    def test_identity_rules(self) -> None:
        with self.assertRaises(mc.ConfigError):
            mc.validate(mc.parse(BASE.replace("slug: atlas", "slug: Bad_Slug")))
        with self.assertRaises(mc.ConfigError):
            mc.validate(mc.parse(BASE.replace("5b5101d1-0f4c-4b7e-9a35-2d6f1f0c7a11", "nope")))

    def test_get(self) -> None:
        config = mc.parse(BASE + "api:\n  dir: api\n  port: 8000\n")
        self.assertEqual(mc.get(config, "api.port"), 8000)
        self.assertIsNone(mc.get(config, "plugin.dir"))
        self.assertEqual(mc._format(None), "")


class SchemaParityTest(unittest.TestCase):
    """The hand-written validator and the JSON schema must agree (skipped without jsonschema and PyYAML)."""

    def test_agree_on_cases(self) -> None:
        try:
            import json

            import jsonschema
            import yaml
        except ImportError:
            self.skipTest("jsonschema or PyYAML missing")
        schema = json.loads((ROOT / "miniapp.schema.json").read_text())
        good = [
            BASE,
            BASE + "api:\n  dir: api\n  port: 8000\nservices:\n  postgres: true\n",
            BASE + "plugin:\n  dir: p\n  build: b\n  out: dist\n  file: a.mjs\n",
            (ROOT / "docs" / "miniapp.example.yaml").read_text(),
        ]
        bad = [
            BASE.replace("version: 2", "version: 1") + "api:\n  dir: api\n  port: 80\n",
            BASE + "api:\n  dir: api\n  port: 0\n",
            BASE + "api:\n  dir: /abs\n  port: 80\n",
            BASE + "services:\n  postgres: true\n",
            BASE + "plugin:\n  dir: p\n  build: b\n  out: dist\n  file: a.zip\n",
            BASE + "miniapp:\n  dir: m\n  out: dist\n",
        ]
        for text in good:
            jsonschema.validate(yaml.safe_load(text), schema)
            mc.validate(mc.parse(text))
        for text in bad:
            with self.assertRaises(jsonschema.ValidationError):
                jsonschema.validate(yaml.safe_load(text), schema)
            with self.assertRaises(mc.ConfigError):
                mc.validate(mc.parse(text))


if __name__ == "__main__":
    unittest.main()
