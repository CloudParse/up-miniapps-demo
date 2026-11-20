"""Runs the shell steps of the deploy workflows against a mock platform, as the runner would (checkout excluded)."""

import json
import os
import re
import shutil
import subprocess
import sys
import base64
import gzip
import tempfile
import unittest
import unittest.mock
from pathlib import Path

import yaml  # PyYAML is required here (check.sh installs it with uv when missing); the test must fail loudly without it

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).parent))

from mock_server import MockServer  # noqa: E402

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
  build: "mkdir -p dist && printf '<html>hello</html>' > dist/index.html && base64 < dist/index.html | gzip > dist/index.base64.gz"
  out: dist
plugin:
  dir: plugin
  build: "mkdir -p dist && printf 'export default 1;' > dist/plugin.mjs"
  out: dist
  file: plugin.mjs
"""
SECRET = "topsecret"
# Built from pieces so that this file does not contain the words it forbids elsewhere.
FORBIDDEN = ("DEL" + "ETE", "pru" + "ne", "--ke" + "ep", "registry_" + "pru" + "ne", "/pack" + "ages")


def workflow(name: str) -> dict:
    return yaml.safe_load((ROOT / ".gitea" / "workflows" / name).read_text())


def jobs_of(name: str) -> dict[str, dict]:
    return workflow(name)["jobs"]


def steps_of(name: str, job: str | None = None) -> list[dict]:
    """The steps of one job, or of the first job when none is named (the frontend and plugin workflows have one job)."""
    jobs = jobs_of(name)
    return jobs[job]["steps"] if job else next(iter(jobs.values()))["steps"]


def expand(value: str, context: dict[str, str]) -> str:
    return re.sub(r"\$\{\{\s*([\w.]+)\s*\}\}", lambda m: context[m.group(1)], str(value))


class Run:
    def __init__(self, ok: bool, failed_step: str, log: str) -> None:
        self.ok, self.failed_step, self.log = ok, failed_step, log


class WorkflowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.src = Path(self.tmp.name) / "src"
        shutil.copytree(ROOT / ".gitea", self.src / ".gitea", ignore=shutil.ignore_patterns("tests", "__pycache__"))
        (self.src / "miniapp.yaml").write_text(CONFIG)
        (self.src / "miniapp").mkdir()
        (self.src / "plugin").mkdir()
        patcher = unittest.mock.patch.dict(os.environ, {"UP_CI_ALLOW_HTTP": "true"})
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_workflow(self, name: str, context: dict[str, str], *, ignore_outputs: bool = False, extra_env: dict | None = None) -> Run:
        """Runs the jobs in order, as the runner would: a job sees the outputs of the jobs it needs, a job whose `if` is false is skipped.
        The checkout is replaced by the prepared `src` folder."""
        job_outputs: dict[str, dict[str, str]] = {}
        log = ""
        for job_name, job in jobs_of(name).items():
            condition = job.get("if")
            if condition is not None:
                match = re.fullmatch(r"needs\.(\w+)\.outputs\.(\w+) != 'true'", condition)
                self.assertTrue(match, f"unsupported job condition {condition!r}")
                self.assertIn(match.group(1), job_outputs, f"job {job_name} reads the outputs of a job it does not run after")
                if job_outputs[match.group(1)].get(match.group(2)) == "true":
                    continue
            outputs: dict[str, str] = {}
            for step in job["steps"]:
                condition = step.get("if")
                if condition is not None:
                    match = re.fullmatch(r"steps\.(\w+)\.outputs\.(\w+) != 'true'", condition)
                    self.assertTrue(match, f"unsupported condition {condition!r}")
                    if not ignore_outputs and outputs.get(f"{match.group(1)}.{match.group(2)}") == "true":
                        continue
                if step["name"] == "Check out the repository":
                    continue
                out_file = Path(self.tmp.name) / "github_output"
                out_file.write_text("")
                step_context = {**context, **{f"steps.{key.split('.')[0]}.outputs.{key.split('.')[1]}": value for key, value in outputs.items()}}
                env = {**os.environ, **(extra_env or {}), **{k: expand(v, step_context) for k, v in step.get("env", {}).items()}}
                env["GITHUB_OUTPUT"] = str(out_file)
                cwd = self.src if step.get("working-directory") == "src" else Path(self.tmp.name)
                self.assertEqual(step.get("shell"), "bash", f"{step['name']} must name its shell")
                result = subprocess.run(["bash", "-c", expand(step["run"], step_context)], cwd=cwd, env=env, capture_output=True, text=True)  # noqa: S603, S607
                log += result.stdout + result.stderr
                self.assertNotIn(SECRET, result.stdout + result.stderr, f"a secret was printed by {step['name']}")
                if result.returncode:
                    return Run(False, step["name"], log)
                for line in out_file.read_text().splitlines():
                    key, _, value = line.partition("=")
                    outputs[f"{step.get('id')}.{key}"] = value
            # the job outputs: `${{ steps.<id>.outputs.<key> }}`, empty when the step wrote nothing
            job_outputs[job_name] = {
                key: re.sub(r"\$\{\{\s*steps\.(\w+)\.outputs\.(\w+)\s*\}\}", lambda m: outputs.get(f"{m.group(1)}.{m.group(2)}", ""), expr)
                for key, expr in job.get("outputs", {}).items()
            }
        return Run(True, "", log)

    def platform(self) -> MockServer:
        def responder(method: str, path: str, headers: dict, body: bytes):
            return (200, {"token": "jwt"}) if path.endswith("/ci/token") else (201, {})

        return MockServer(responder)

    def context(self, server: MockServer, version: str = "1.0.4") -> dict[str, str]:
        return {
            "inputs.version": version,
            "secrets.UP_API_URL": server.url,
            "secrets.REGISTRY_USER": "ci",
            "secrets.REGISTRY_TOKEN": SECRET,
            "gitea.repository": "demo/Demo-Atlas-5b51",
            "gitea.server_url": "https://git.example",
            "gitea.repository_owner": "demo",
            "gitea.token": SECRET,
            "gitea.sha": "0" * 40,
        }

    def calls(self, server: MockServer) -> list[tuple[str, str]]:
        return [(c["method"], c["path"]) for c in server.calls]

    def without_section(self, section: str) -> None:
        lines, skipping = [], False
        for line in CONFIG.splitlines():
            if line.startswith(f"{section}:"):
                skipping = True
                continue
            if skipping and line.startswith("  "):
                continue
            skipping = False
            lines.append(line)
        (self.src / "miniapp.yaml").write_text("\n".join(lines) + "\n")

    # --- the exact sequence of platform calls ---------------------------------------------------------------

    def test_frontend_calls_token_then_publish_and_nothing_else(self) -> None:
        with self.platform() as server:
            result = self.run_workflow("deploy-frontend.yml", self.context(server))
        self.assertTrue(result.ok, result.log)
        self.assertEqual(self.calls(server), [("POST", "/ci/token"), ("POST", f"/admin/applications/{APP}/artifacts")])
        published = (self.src / "dist-ci" / "miniapp-1.0.4.base64.gz").read_bytes()
        self.assertEqual(base64.b64decode(gzip.decompress(published)), b"<html>hello</html>", "what the shell and the web launcher decode")
        self.assertFalse(list((self.src / "dist-ci").glob("plugin-*")))

    def test_plugin_calls_token_then_publish_and_nothing_else(self) -> None:
        with self.platform() as server:
            result = self.run_workflow("deploy-plugin.yml", self.context(server))
        self.assertTrue(result.ok, result.log)
        self.assertEqual(self.calls(server), [("POST", "/ci/token"), ("POST", f"/admin/applications/{APP}/backoffice-plugin/artifacts")])
        self.assertTrue((self.src / "dist-ci" / "plugin-1.0.4.mjs").exists())

    def backend_run(self, extra_env: dict | None = None, version: str = "1.0.3") -> tuple[Run, MockServer, Path]:
        (self.src / "api").mkdir(exist_ok=True)
        (self.src / "api" / "Dockerfile").write_text("FROM scratch\n")
        fake = Path(self.tmp.name) / "kaniko"
        args_file = Path(self.tmp.name) / "args"
        fake.write_text(f'#!/bin/sh\nprintf "%s\\n" "$@" > {args_file}\n')
        fake.chmod(0o755)
        env = {
            "KANIKO_EXECUTOR": str(fake),
            "KANIKO_DOCKER_CONFIG": str(Path(self.tmp.name) / "docker"),
            "CI_REGISTRY_HOST": "git.demo.example",
            "CI_REGISTRY_INSECURE": "true",
            **(extra_env or {}),
        }
        with self.platform() as server:
            result = self.run_workflow("deploy-backend.yml", self.context(server, version), extra_env=env)
        return result, server, args_file

    def test_backend_pushes_then_deploys_the_tag_as_the_last_call(self) -> None:
        result, server, args_file = self.backend_run()
        self.assertTrue(result.ok, result.log)
        kaniko_args = args_file.read_text().split()
        self.assertIn("git.demo.example/demo/demo-atlas-5b51:1.0.3", kaniko_args)
        self.assertIn("--insecure", kaniko_args)
        self.assertIn("API_PORT=8000", kaniko_args)
        self.assertEqual(self.calls(server), [("POST", "/ci/token"), ("POST", f"/admin/applications/{APP}/custom-component/deploy")])
        self.assertEqual(json.loads(server.calls[-1]["body"]), {"tag": "1.0.3"})

    def test_backend_without_a_registry_host_fails_and_calls_nothing(self) -> None:
        (self.src / "api").mkdir(exist_ok=True)
        (self.src / "api" / "Dockerfile").write_text("FROM scratch\n")
        with self.platform() as server:
            result = self.run_workflow("deploy-backend.yml", self.context(server), extra_env={"KANIKO_EXECUTOR": "/nonexistent"})
        self.assertFalse(result.ok)
        self.assertEqual(result.failed_step, "Build and push the image")
        self.assertIn("CI_REGISTRY_HOST", result.log)
        self.assertEqual(server.calls, [])

    def test_registry_insecure_comes_only_from_the_runner_variable(self) -> None:
        result, _, args_file = self.backend_run({"CI_REGISTRY_INSECURE": "false"})
        self.assertTrue(result.ok, result.log)
        self.assertNotIn("--insecure", args_file.read_text().split())

    # --- the version ------------------------------------------------------------------------------------------

    def test_a_bad_version_stops_at_the_first_step_in_every_workflow(self) -> None:
        for name in ("deploy-backend.yml", "deploy-frontend.yml", "deploy-plugin.yml"):
            for job in jobs_of(name):
                self.assertEqual(steps_of(name, job)[0]["name"], "Check the version", f"{name}/{job}")
            for bad in ("latest", "1.0", "1.0.0\n--x", '1.0.0"; name="x', "../1.0.0", "01.0.0", "1.0.0-rc1", " 1.0.0", ""):
                with self.subTest(name=name, version=bad), self.platform() as server:
                    result = self.run_workflow(name, self.context(server, bad))
                    self.assertFalse(result.ok)
                    self.assertEqual(result.failed_step, "Check the version")
                    self.assertEqual(server.calls, [])

    # --- absent sections and invalid files --------------------------------------------------------------------

    def test_each_workflow_succeeds_and_does_nothing_without_its_section(self) -> None:
        for name, section in {"deploy-backend.yml": "api", "deploy-frontend.yml": "miniapp", "deploy-plugin.yml": "plugin"}.items():
            with self.subTest(name), self.platform() as server:
                self.without_section(section)
                shutil.rmtree(self.src / "dist-ci", ignore_errors=True)
                result = self.run_workflow(name, self.context(server), extra_env={"KANIKO_EXECUTOR": "/nonexistent-must-not-run"})
                self.assertTrue(result.ok, result.log)
                self.assertEqual(server.calls, [])
                self.assertFalse((self.src / "dist-ci").exists())
                self.assertEqual(result.log.count("::notice::"), 1, "the notice is printed once")
                self.assertIn(f"no `{section}` section", result.log)

    def test_an_invalid_file_fails_the_run_at_the_read_step(self) -> None:
        invalid = {
            "unknown key": CONFIG + "extra: 1\n",
            "version 1 with sections": CONFIG.replace("version: 2", "version: 1"),
            "line separator": CONFIG.replace("name: Atlas", "name: Atlas api2: x"),
            "bad port": CONFIG.replace("port: 8000", "port: 80"),
        }
        for label, text in invalid.items():
            for name in ("deploy-backend.yml", "deploy-frontend.yml", "deploy-plugin.yml"):
                with self.subTest(label=label, workflow=name), self.platform() as server:
                    (self.src / "miniapp.yaml").write_text(text)
                    result = self.run_workflow(name, self.context(server))
                    self.assertFalse(result.ok, "an invalid file must fail the run, never skip it")
                    self.assertEqual(result.failed_step, "Read miniapp.yaml")
                    self.assertEqual(server.calls, [])

    def test_a_broken_skip_signal_fails_closed(self) -> None:
        """If the step output never arrives, the build steps run and fail on the missing section: no silent success."""
        self.without_section("miniapp")
        with self.platform() as server:
            result = self.run_workflow("deploy-frontend.yml", self.context(server), ignore_outputs=True)
        self.assertFalse(result.ok)
        self.assertEqual(server.calls, [])

    # --- secrets ----------------------------------------------------------------------------------------------

    def test_builds_run_with_a_scrubbed_environment(self) -> None:
        probe = Path(self.tmp.name) / "env.txt"
        config = CONFIG.replace(
            "build: \"mkdir -p dist && printf '<html>hello</html>' > dist/index.html && base64 < dist/index.html | gzip > dist/index.base64.gz\"",
            f"build: env > {probe} && mkdir -p dist && printf hello > dist/index.html && base64 < dist/index.html | gzip > dist/index.base64.gz",
        )
        (self.src / "miniapp.yaml").write_text(config)
        leak = {"CI_REGISTRY_HOST": "leak", "CI_GITEA_URL": "leak", "UP_JOB_TOKEN": "leak", "GITEA_TOKEN": "leak", "REGISTRY_TOKEN": "leak"}
        with self.platform() as server:
            result = self.run_workflow("deploy-frontend.yml", self.context(server), extra_env=leak)
        self.assertTrue(result.ok, result.log)
        seen = {line.split("=", 1)[0] for line in probe.read_text().splitlines()}
        self.assertFalse(seen & set(leak), f"the build saw {seen & set(leak)}")
        self.assertNotIn(os.environ.get("HOME", "/nonexistent-home"), probe.read_text().split("HOME=")[1].splitlines()[0])

    def test_secrets_are_referenced_only_by_the_steps_that_need_them(self) -> None:
        allowed = {
            "deploy-backend.yml": {"build": {"Build and push the image": "REGISTRY_"}, "release": {"Deploy the component": "UP_"}},
            "deploy-frontend.yml": {"deploy-frontend": {"Publish": "UP_"}},
            "deploy-plugin.yml": {"deploy-plugin": {"Publish": "UP_"}},
        }
        for name, per_job in allowed.items():
            self.assertEqual(set(jobs_of(name)), set(per_job), f"{name}: the jobs changed, update this test")
            for job, per_step in per_job.items():
                for step in steps_of(name, job):
                    used = {m for m in re.findall(r"secrets\.(\w+)", json.dumps(step))}
                    if step["name"] in per_step:
                        self.assertTrue(used and all(u.startswith(per_step[step["name"]]) for u in used), (name, job, step["name"], used))
                    else:
                        self.assertFalse(used, f"{name}/{job}: step {step['name']!r} must not see secrets: {used}")

    def test_the_build_job_never_sees_the_platform_credentials_and_the_release_job_never_sees_the_registry_token(self) -> None:
        build = json.dumps(jobs_of("deploy-backend.yml")["build"])
        release = json.dumps(jobs_of("deploy-backend.yml")["release"])
        for word in ("UP_JOB_TOKEN", "UP_REPOSITORY", "UP_API_URL"):
            self.assertNotIn(word, build, "the steps that run your Dockerfile are not given the platform call")
        for word in ("REGISTRY_TOKEN", "REGISTRY_USER"):
            self.assertNotIn(word, release)

    def test_the_job_token_goes_to_the_checkout_and_to_the_platform_call_only(self) -> None:
        """The job token is the only credential of the mini-app: no secret of the mini-app is in the repository any more."""
        allowed = {
            "deploy-backend.yml": {"Check out the repository", "Deploy the component"},
            "deploy-frontend.yml": {"Check out the repository", "Publish"},
            "deploy-plugin.yml": {"Check out the repository", "Publish"},
        }
        for name, steps_allowed in allowed.items():
            for job in jobs_of(name):
                for step in steps_of(name, job):
                    uses = "gitea.token" in json.dumps(step) or "github.token" in json.dumps(step)
                    if step["name"] in steps_allowed:
                        continue
                    self.assertFalse(uses, f"{name}/{job}: step {step['name']!r} must not be given the job token")
            text = (ROOT / ".gitea" / "workflows" / name).read_text()
            for word in ("UP_CLIENT_ID", "UP_CLIENT_SECRET", "clientSecret", "secrets.GITEA_TOKEN"):
                self.assertNotIn(word, text, f"{name}: the mini-app has no secret of its own in the repository")

    def test_the_platform_gets_the_job_token_and_the_repository_of_the_job(self) -> None:
        with self.platform() as server:
            result = self.run_workflow("deploy-frontend.yml", self.context(server))
            self.assertTrue(result.ok, result.log)
            token_call = next(c for c in server.calls if c["path"].endswith("/ci/token"))
        body = json.loads(token_call["body"])
        self.assertEqual(body["jobToken"], SECRET)
        self.assertEqual(body["repository"], "demo/Demo-Atlas-5b51")
        self.assertEqual(set(body), {"applicationUuid", "repository", "jobToken"})
        self.assertNotIn(SECRET, result.log, "the token is never printed")

    # --- the two jobs of the backend workflow -----------------------------------------------------------------

    def test_kaniko_is_the_last_step_of_the_build_job(self) -> None:
        """Kaniko replaces the file system of the runner container: nothing may run after it in the same job."""
        steps = steps_of("deploy-backend.yml", "build")
        self.assertEqual(steps[-1]["name"], "Build and push the image")
        self.assertIn("build-image.sh", steps[-1]["run"])
        for job, other in jobs_of("deploy-backend.yml").items():
            if job != "build":
                self.assertNotIn("build-image.sh", json.dumps(other))
                self.assertNotIn("kaniko", json.dumps(other).lower())

    def test_the_job_that_asks_the_platform_for_a_session_has_the_name_the_platform_expects(self) -> None:
        """The platform (up/backend giteaaccess.CIJobs) gives a session only to this job of each workflow: the name is part of the contract."""
        expected = {"deploy-backend.yml": "release", "deploy-frontend.yml": "deploy-frontend", "deploy-plugin.yml": "deploy-plugin"}
        for workflow, job in expected.items():
            with self.subTest(workflow=workflow):
                steps = jobs_of(workflow)[job]["steps"]
                self.assertTrue(any("UP_JOB_TOKEN" in json.dumps(step.get("env", {})) for step in steps), "the job asks the platform with its token")
        for job, body in jobs_of("deploy-backend.yml").items():
            if job != "release":
                self.assertNotIn("UP_JOB_TOKEN", json.dumps(body), "no other job of the backend workflow holds the platform token")

    def test_the_release_job_runs_after_the_build_and_only_when_it_built(self) -> None:
        release = jobs_of("deploy-backend.yml")["release"]
        self.assertEqual(release["needs"], "build")
        self.assertEqual(release["if"], "needs.build.outputs.skip != 'true'")
        self.assertEqual(jobs_of("deploy-backend.yml")["build"]["outputs"], {"skip": "${{ steps.plan.outputs.skip }}"})
        for job in ("build", "release"):
            self.assertEqual(steps_of("deploy-backend.yml", job)[0]["name"], "Check the version")

    def test_the_release_job_does_not_run_when_the_build_job_skips(self) -> None:
        self.without_section("api")
        with self.platform() as server:
            result = self.run_workflow("deploy-backend.yml", self.context(server), extra_env={"KANIKO_EXECUTOR": "/nonexistent-must-not-run"})
        self.assertTrue(result.ok, result.log)
        self.assertEqual(server.calls, [], "the release job must not call the platform when the build was skipped")

    def test_a_failed_build_job_calls_nothing(self) -> None:
        (self.src / "api").mkdir(exist_ok=True)
        (self.src / "api" / "Dockerfile").write_text("FROM scratch\n")
        with self.platform() as server:
            result = self.run_workflow("deploy-backend.yml", self.context(server), extra_env={"CI_REGISTRY_HOST": "git.demo.example", "KANIKO_EXECUTOR": "/nonexistent"})
        self.assertFalse(result.ok)
        self.assertEqual(result.failed_step, "Build and push the image")
        self.assertEqual(server.calls, [])

    # --- shape ------------------------------------------------------------------------------------------------

    def test_workflows_declare_dispatch_runner_and_shell(self) -> None:
        for name in ("deploy-backend.yml", "deploy-frontend.yml", "deploy-plugin.yml"):
            wf = workflow(name)
            triggers = wf.get("on", wf.get(True))
            self.assertEqual(list(triggers), ["workflow_dispatch"])
            self.assertEqual(list(triggers["workflow_dispatch"]["inputs"]), ["version"])
            for job, definition in wf["jobs"].items():
                self.assertEqual(definition["runs-on"], "up-ci", f"{name}/{job}")
                for step in definition["steps"]:
                    self.assertEqual(step.get("shell"), "bash")

    def test_nothing_removes_anything_anywhere_including_the_tests(self) -> None:
        folders = [ROOT / ".gitea" / "workflows", ROOT / ".gitea" / "scripts", ROOT / ".gitea" / "scripts" / "tests"]
        for folder in folders:
            for path in folder.iterdir():
                if path.is_file() and path.suffix in {".py", ".sh", ".yml"}:
                    text = path.read_text()
                    for word in FORBIDDEN:
                        self.assertNotIn(word, text, f"{word!r} in {path.relative_to(ROOT)}")


if __name__ == "__main__":
    unittest.main()
