---
name: up-miniapp-ci-contract
description: MANDATORY before any change in this repository, and again before calling a task done. The files nobody may change (the deployment CI, the agent skills and settings, the rule files), the forbidden actions, and what the CI relies on in the files you do change (miniapp.yaml, the api/ Dockerfile, the miniapp/ build, lock files, ports, health route). Breaking one of these rules makes the mini-app impossible to deploy from the Studio. Ends with the checks to run and the security review to launch.
---

# CI contract of the mini-app

Why this skill exists:
- The Studio buttons start the workflows of `.gitea/workflows/`. The platform and those workflows expect fixed names, files and formats.
- If one of them changes, the next deployment fails. Often nothing fails locally: the break shows only at the deploy click.
- When a task seems to need a protected file or a forbidden action, stop. Tell the user which rule blocks it. Only a maintainer of the project changes these files.

Details: `AGENTS.md` section 5.1 and `docs/deploy.md`. When this skill and the repository disagree, the repository wins: report the difference.

## 1. Protected files: never modify, create, rename or delete

| Path | Why |
| --- | --- |
| `.gitea/` (workflows, scripts, tests) | The deployment CI. The platform starts these workflows by file name and job name. |
| `.gitlab-ci.yml` | The mirror job of the template. |
| `miniapp.schema.json` | The format the CI validates `miniapp.yaml` against. |
| `.claude/` (skills, agents, hooks, `settings.json`) | The agent rules and their guard rails. |
| `AGENTS.md`, `CLAUDE.md` (every folder) | The project rules. |

Also forbidden for these files:
- Deleting a workflow you do not use. A workflow without its section in `miniapp.yaml` ends green and builds nothing.
- Getting around the protection: shell redirections, `sed -i`, scripts, `git checkout` or `git restore`, a new settings file, or turning hooks off.

`.claude/settings.json` denies these edits and `.claude/hooks/guard.py` blocks them. Those are guard rails for agents, not the boundary. The review of section 4 also checks them.

## 2. Forbidden actions

- Reading, printing, copying or sending a secret: `api/.env` and any `.env*` file except `*.env.template`, the environment (`env`, `printenv`), tokens. Use `uv run --env-file .env ...`.
- Sending code, data or secrets to an outside service: no new outbound URL, no telemetry, no paste site, no upload.
- Weakening a check: auth, token checks (`alg`, `exp`, `aud`), tests, lint rules, type checks, `--no-verify`, `# type: ignore`, `# noqa`, `biome-ignore` added to pass.
- Hidden or harmful code: backdoors, hidden routes, obfuscated or encoded code, miners, code that runs a downloaded script (`curl ... | sh`).
- Destroying work: `git push --force`, history rewrites, deleting branches or tags, `rm -rf` outside the project.
- Adding a secret, a new CI secret or an environment variable to `miniapp.yaml`.

## 3. Rules for the files you may change

### `miniapp.yaml` (root)
- `uuid` and `slug`: never change them. The platform wrote them. The CI calls the platform with this `uuid`.
- The placeholder `uuid` `00000000-0000-0000-0000-000000000000` is refused by every workflow. Never write it back.
- Keep the file at the root, named `miniapp.yaml`.
- Keys: only the keys of `miniapp.schema.json`. An unknown key fails every workflow.
- Format read by a strict parser (`.gitea/scripts/miniapp_config.py`):
  - no quoted keys, no tabs, no control characters;
  - no anchors, no multi-line strings, no backslash escapes;
  - lists as `[a, b]` or `- a` only.
- Paths (`dir`, `out`, `file`): relative, plain segments. No leading `/` or `-`. No `.`, `..`, `.git`, `dist-ci` segment. No `//`.
- `api.port`: 1024 to 65535. It is the port the image listens on.
- `version: 2` is needed for the deployment sections (`api`, `services`, `miniapp`, `plugin`).
- Never a secret or an environment variable in the file.

### `api/` (backend workflow)
- `api/Dockerfile` stays in the folder `api.dir`. The CI builds it with Kaniko. There is no Docker daemon.
- The app listens on `SERVER_PORT`. In the `Dockerfile`, keep `ARG API_PORT` and `SERVER_PORT=${API_PORT}`. The CI sets `API_PORT` from `api.port`. Never replace them with a literal port.
- The route of `api.healthPath` (`/healthz`, `api/app/api/routes/health.py`) must answer 200 without a token. The platform probes it. Never protect, rename or remove it without changing `api.healthPath`.
- `uv.lock` is committed and matches `pyproject.toml`. The image runs `uv sync --frozen`, which does not check the lock: a stale lock ships old dependencies. After a dependency change run `uv lock`, commit the lock, and run `uv lock --check`.
- The image copies only `pyproject.toml`, `uv.lock`, `app/` and `configs/`. A new folder needed at run time must be added to the `Dockerfile`.
- Keep: pinned base images (tag and digest), user `10001`, `/app` read-only, `ENVIRONMENT=production`, `CMD ["python", "-m", "app"]` or an exec-form `api.command`.
- `ENVIRONMENT` stays `production` in the `Dockerfile`, and is never set in the Studio component variables: `development` serves `/docs`, the demo routes and local CORS. The default of `configs/config.toml` is `production` (fail closed).
- The API refuses to start in production on the DEV defaults (`HUB_APP_UUID`, `HUB_CLIENT_SECRET`). Never remove that check.

### `miniapp/` (frontend workflow)
- `npm run build` must run `up-sdk build`. The CI publishes `out/index.base64.gz`, which only `up-sdk build` writes. Without it the job fails.
- `out` is `dist`. Keep `miniapp.yaml` `miniapp.out` equal to the real output folder.
- The CI runs `npm ci`: `package-lock.json` is committed and matches `package.json`. After a dependency change run `npm install` and commit the lock.
- The build runs with an empty environment (`run-build.sh`, `env -i`). It must not need any environment variable or secret. In a production build `miniapp/src/config/env.ts` reads no variable (the `import.meta.env.PROD` branch).
- Size limits: `index.base64.gz` at most 18 MiB, the HTML at most 64 MiB.

### `plugin/` (plugin workflow, only with a `plugin` section)
- One `.js` or `.mjs` file of at most 5 MiB, at `<plugin.dir>/<plugin.out>/<plugin.file>`.

### Development ports
- API `0.0.0.0:21514`, Vite `21515`, plugin `21516`. The Coder workspace opens 21515. Do not change them.

## 4. Checks, then the security review

This list is the reference. `AGENTS.md` section 6 points here.

```bash
# from the repository root; the lock check comes first because `uv run` re-locks
(cd api && uv lock --check)
(cd api && uv run ruff format . && uv run ruff check . && uv run mypy app tests && uv run pytest)
(cd miniapp && npm ci)                              # when miniapp/package.json changed: fails if package-lock.json is out of sync
(cd miniapp && npm run check:write && npm run typecheck && npm run build && test -f dist/index.base64.gz)
python3 .gitea/scripts/miniapp_config.py validate   # in a mini-app project; the template fails it on purpose (placeholder uuid)
```

Then check that no protected file changed. This command must print nothing:

```bash
git status --porcelain -- .gitea .gitlab-ci.yml miniapp.schema.json .claude ':(glob)**/AGENTS.md' ':(glob)**/CLAUDE.md'
```

Last step of every task:
1. Run the review of `AGENTS.md` section 7 on the whole diff.
2. Launch the subagent `up-security-reviewer` (`.claude/agents/up-security-reviewer.md`) on the same diff. It is a second, independent check. Without Claude Code, follow that file yourself as a separate pass.
3. Fix every Blocking finding. Run the checks again.
4. Report both reviews before calling the task done.
