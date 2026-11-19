import json
import sys
import unittest
from pathlib import Path

import jsonschema  # the tests need PyYAML and jsonschema: check.sh installs them with uv when they are missing
import yaml

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / ".gitea" / "scripts"))

import miniapp_config as mc  # noqa: E402

SCHEMA = json.loads((ROOT / "miniapp.schema.json").read_text())
BASE = """version: 2
uuid: 5b5101d1-0f4c-4b7e-9a35-2d6f1f0c7a11
slug: atlas
name: Atlas
"""


def check(extra: str) -> None:
    mc.validate(mc.parse(BASE + extra))


def refused(text: str) -> bool:
    try:
        mc.validate(mc.parse(text))
    except mc.ConfigError:
        return True
    return False


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

    def test_crlf_lines_are_accepted(self) -> None:
        mc.validate(mc.parse(BASE.replace("\n", "\r\n")))

    def test_block_list_and_nesting(self) -> None:
        config = mc.parse("api:\n  command:\n    - python\n    - -m\n  port: 8000\n")
        self.assertEqual(config["api"], {"command": ["python", "-m"], "port": 8000})

    def test_refuses_every_control_and_line_separator_character(self) -> None:
        for char in ("\u2028", "\u2029", "\u0085", "\x0b", "\x0c", "\x1c", "\x1d", "\x1e", "\x00", "\t", "\ufeff", "\u202e"):
            with self.subTest(hex(ord(char))), self.assertRaisesRegex(mc.ConfigError, "control character"):
                mc.parse(f"name: a{char}b\n")

    def test_a_lone_carriage_return_is_refused(self) -> None:
        with self.assertRaises(mc.ConfigError):
            mc.parse("name: a\rapi:\n")

    def test_line_separator_cannot_hide_a_section(self) -> None:
        """PyYAML would read U+2028 as a line break: the file must be refused, not read differently by two parsers."""
        hidden = BASE + "# comment\u2028api:\n  dir: api\n  port: 8000\n"
        with self.assertRaises(mc.ConfigError):
            mc.parse(hidden)

    def test_refuses_quoted_keys_missing_space_and_odd_syntax(self) -> None:
        cases = {
            "quoted key": '"api":\n  dir: a\n',
            "single quoted key": "'api': 1\n",
            "no space after the colon": "dir:api\n",
            "key with a space": "my key: 1\n",
            "duplicate": "a: 1\na: 2\n",
            "anchor": "a: &x 1\n",
            "block scalar": "a: |\n  text\n",
            "alias": "a: *x\n",
            "unterminated list": "a: [1, 2\n",
            "unterminated string": 'a: "abc\n',
            "text after a quote": 'a: "abc" def\n',
            "escape": 'a: "line\\nbreak"\n',
            "doubled single quote": "a: 'it''s'\n",
            "quote inside a plain value": "a: don't\n",
            "colon space in a plain value": "a: b: c\n",
            "odd indent": "a:\n   b: 1\n",
            "empty list item": "a:\n  - \n",
            "nested list": "a: [[1]]\n",
        }
        for name, text in cases.items():
            with self.subTest(name), self.assertRaises(mc.ConfigError):
                mc.parse(text)

    def test_hash_inside_quotes_is_not_a_comment_and_after_a_plain_value_is(self) -> None:
        config = mc.parse('a: "x # y"\nb: plain # comment\nc: [ "p # q", r ] # tail\n')
        self.assertEqual((config["a"], config["b"], config["c"]), ("x # y", "plain", ["p # q", "r"]))

    def test_example_in_docs_is_valid(self) -> None:
        config = mc.load(ROOT / "docs" / "miniapp.example.yaml")
        mc.validate(config)
        self.assertEqual(mc.plan(config, "backend"), "run")
        self.assertEqual(mc.plan(config, "frontend"), "run")
        self.assertTrue(mc.plan(config, "plugin").startswith("skip "))  # the example's plugin section is commented out

    def test_invalid_utf8_is_refused(self) -> None:
        path = ROOT / ".gitea" / "scripts" / "tests" / "_bad_utf8.yaml"
        path.write_bytes(b"name: \xff\xfe\n")
        self.addCleanup(path.unlink)
        with self.assertRaisesRegex(mc.ConfigError, "UTF-8"):
            mc.load(path)


class ValidateTest(unittest.TestCase):
    def test_unknown_top_level_key_is_refused(self) -> None:
        for key in ("api2: 1", "extra: x", "Api:\n  dir: a"):
            with self.subTest(key), self.assertRaisesRegex(mc.ConfigError, "unknown key"):
                check(key + "\n")

    def test_v1_is_valid_and_every_target_is_skipped(self) -> None:
        config = mc.parse(BASE.replace("version: 2", "version: 1"))
        mc.validate(config)
        for target in mc.TARGETS:
            self.assertTrue(mc.plan(config, target).startswith("skip "))

    def test_v1_with_deploy_sections_refused(self) -> None:
        with self.assertRaisesRegex(mc.ConfigError, "api: needs `version: 2`"):
            mc.validate(mc.parse(BASE.replace("version: 2", "version: 1") + "api:\n  dir: api\n  port: 8080\n"))

    def test_plan_is_per_section(self) -> None:
        config = mc.parse(BASE + "api:\n  dir: api\n  port: 8000\nplugin:\n  dir: p\n  build: b\n  out: dist\n  file: a.mjs\n")
        self.assertEqual(mc.plan(config, "backend"), "run")
        self.assertEqual(mc.plan(config, "plugin"), "run")
        self.assertRegex(mc.plan(config, "frontend"), r"^skip .*`miniapp` section")
        with self.assertRaises(mc.ConfigError):
            mc.plan(config, "nope")

    def test_an_invalid_file_never_becomes_a_skip(self) -> None:
        """Fail closed: every kind of invalid file raises for every target, none returns `skip`."""
        invalid = [
            BASE + "api:\n  dir: api\n  port: 0\n",
            BASE + "extra: 1\n",
            BASE.replace("slug: atlas", "slug: BAD"),
            "name: only a name\n",
            BASE + "services:\n  postgres: true\n",
        ]
        for text in invalid:
            for target in mc.TARGETS:
                with self.subTest(text=text[:40], target=target), self.assertRaises(mc.ConfigError):
                    mc.plan(mc.parse(text), target)

    def test_cli_exit_codes(self) -> None:
        for text, code in ((BASE, 0), (BASE + "extra: 1\n", 1), ("a:b\n", 1)):
            path = ROOT / ".gitea" / "scripts" / "tests" / "_cli.yaml"
            path.write_text(text)
            self.addCleanup(path.unlink, missing_ok=True)
            self.assertEqual(mc.main(["plan", "--target", "backend", "--file", str(path)]), code)
        self.assertEqual(mc.main(["get", "api.dir", "--file", str(ROOT / ".gitea" / "scripts" / "tests" / "missing.yaml")]), 1)

    PATHS_REFUSED = ("../a", "a/../b", "/abs", ".", "..", "-rf", "a/-b", "a//b", "a/", ".git", "a/.git/x", "dist-ci", "x/dist-ci", "a b", "a;b", "$HOME")

    def test_paths(self) -> None:
        for path in self.PATHS_REFUSED:
            with self.subTest(path), self.assertRaises(mc.ConfigError):
                check(f"api:\n  dir: '{path}'\n  port: 8000\n")
        for path in ("api", "a/b", "my-app/api_v2", "a.b", "..a"):
            with self.subTest(path):
                check(f"api:\n  dir: {path}\n  port: 8000\n")

    def test_ports(self) -> None:
        for port in ("80", "1023", "65536", "0", "-1", "true", "abc"):
            with self.subTest(port), self.assertRaises(mc.ConfigError):
                check(f"api:\n  dir: api\n  port: {port}\n")
        for port in ("1024", "8000", "65535"):
            check(f"api:\n  dir: api\n  port: {port}\n")

    def test_version_check(self) -> None:
        for good in ("0.0.0", "1.2.3", "10.20.30"):
            self.assertEqual(mc.check_version(good), good)
        for bad in ("1.2", "01.2.3", "1.2.3-rc1", "1.2.3\n", "1.2.3 ", " 1.2.3", "v1.2.3", "1.2.3.4", "../1.2.3", "1.2.3;id", "", "9" * 12 + ".0.0"):
            with self.subTest(bad), self.assertRaises(mc.ConfigError):
                mc.check_version(bad)

    def test_get(self) -> None:
        config = mc.parse(BASE + "api:\n  dir: api\n  port: 8000\n")
        self.assertEqual(mc.get(config, "api.port"), 8000)
        self.assertIsNone(mc.get(config, "plugin.dir"))
        self.assertEqual(mc._format(None), "")


class SchemaParityTest(unittest.TestCase):
    """The hand-written validator and the JSON schema must accept and refuse the same files."""

    def test_same_keys(self) -> None:
        self.assertEqual(set(SCHEMA["properties"]), set(mc.TOP_LEVEL_KEYS))
        self.assertFalse(SCHEMA["additionalProperties"])
        for section, keys in mc.SECTION_KEYS.items():
            self.assertEqual(set(SCHEMA["properties"][section]["properties"]), set(keys), section)
            self.assertFalse(SCHEMA["properties"][section]["additionalProperties"], section)

    def test_same_patterns_and_limits(self) -> None:
        props = SCHEMA["properties"]
        self.assertEqual(props["api"]["properties"]["dir"]["pattern"], mc.REL_PATH_PATTERN)
        self.assertEqual(props["plugin"]["properties"]["file"]["pattern"], mc.JS_FILE_PATTERN)
        self.assertEqual(props["api"]["properties"]["port"]["minimum"], mc.MIN_PORT)

    def test_agree_on_cases(self) -> None:
        good = [
            BASE,
            BASE + "api:\n  dir: api\n  port: 8000\nservices:\n  postgres: true\n",
            BASE + "plugin:\n  dir: p\n  build: b\n  out: dist\n  file: a.mjs\n",
            BASE + "miniapp:\n  dir: m\n  build: b\n  out: dist\n",
            BASE + "cardStyle: navy\ndarkTheme: null\ndeviceTypes: [PHONE, TV]\nlogo: assets/logo.webp\n",
            (ROOT / "docs" / "miniapp.example.yaml").read_text(),
        ]
        bad = [
            BASE.replace("version: 2", "version: 1") + "api:\n  dir: api\n  port: 8080\n",
            BASE + "api:\n  dir: api\n  port: 80\n",
            BASE + "api:\n  dir: /abs\n  port: 8080\n",
            BASE + "api:\n  dir: ../x\n  port: 8080\n",
            BASE + "api:\n  dir: a//b\n  port: 8080\n",
            BASE + "api:\n  dir: -rf\n  port: 8080\n",
            BASE + "api:\n  dir: .git\n  port: 8080\n",
            BASE + "api:\n  dir: dist-ci\n  port: 8080\n",
            BASE + "services:\n  postgres: true\n",
            BASE + "plugin:\n  dir: p\n  build: b\n  out: dist\n  file: a.zip\n",
            BASE + "miniapp:\n  dir: m\n  out: dist\n",
            BASE + "extra: 1\n",
            BASE + "cardStyle: pink\n",
            BASE + "deviceTypes: [PHONE, PHONE]\n",
            BASE + "logo: a.png\n",
        ]
        for text in good:
            jsonschema.validate(yaml.safe_load(text), SCHEMA)
            mc.validate(mc.parse(text))
        for text in bad:
            with self.subTest(text[-60:]):
                with self.assertRaises(jsonschema.ValidationError):
                    jsonschema.validate(yaml.safe_load(text), SCHEMA)
                self.assertTrue(refused(text))


if __name__ == "__main__":
    unittest.main()
