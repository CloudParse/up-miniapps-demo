# AGENT.md: Up Mini-App Demo

Entry point for every agent and student working in this repository. Read it fully before changing anything, then read the `AGENT.md` of the sub-project you are touching.

Code, comments, docs and commit messages are written in English. The UI text of `miniapp/` is French.

## 1. Purpose

This repository is the **demo project** for teams building an Up mini-app: a web app that runs inside the Up mobile app (the "shell"), plus the API that serves it. Every mini-app project of an organisation starts as a copy of it (its own repository on the organisation's Gitea, its own Coder workspace per member).

- `miniapp/` uses every public capability of `@cloudparse/up-miniapps-sdk` (map and journeys, QR codes, network, realtime, storage, haptics, permissions, account, achievements, payment demo). Its home screen shows the message of the backend route `GET /api/v1/hello`.
- `api/` is a small FastAPI service with public, authenticated and admin routes, wired to the mini-app's own DEV database, cache and bucket.
- `plugin/` is the Studio plugin of the demo: the admin page of the mini-app. It calls the admin routes of `api/` and never holds a credential (`docs/plugin.md`).

The point is the **shape**: a clean architecture, a secure setup and a workflow you can copy for a real idea. The code must itself be an example of what we ask of you.

Where it lives:
- GitLab `CloudParse/up/miniapps/up-miniapps-demo` is the source.
- The manual CI job `github-mirror` (`.gitlab-ci.yml`) pushes `main` to the public GitHub mirror `CloudParse/up-miniapps-demo`.

## 2. Architecture

The project runs in its **Coder workspace** (`docs/coder.md`). The API and the mini-app both run in the workspace. They use the organisation's DEV environment: its backend (the "Hub", with test users) and the mini-app's own database, cache and bucket.

```text
Browser ──Coder app "Mini-app" (private)──▶ miniapp/ (Vite, 21515) ──/api/ proxy──▶ api/ (FastAPI, 0.0.0.0:21514)
                                                 │                                   ├──▶ DEV Hub         http://backend-service:8080/api/v1
                                                 │                                   ├──▶ DEV database    DATABASE_URL
                                                 │                                   ├──▶ DEV cache       CACHE_URL, CACHE_KEY_PREFIX
                                                 │                                   └──▶ DEV bucket      STORAGE_*
                                                 └──/hub/ proxy──▶ DEV Hub (sign in as a test user, development only)
```

In production the Up shell (the phone app) hosts the mini-app:

```text
Up shell (phone)
   │  hosts the mini-app in a WebView; the SDK bridge talks to it
   ▼
miniapp/                           api/                         CloudParse backend ("Hub")
React + SDK  ──HTTP + user token──▶  FastAPI  ──machine-to-machine──▶  the organisation's backend
```

How a request travels:

1. The shell loads `miniapp/` (the single `dist/index.html` built by `up-sdk build`). In a browser, `SDKProvider` mounts the SDK simulator instead.
2. The mini-app calls its API through the SDK (`createApiService`). The URL comes from the shell (`env.backendUrl`, registered on the Hub). In development it comes from `VITE_BACKEND_URL`.
3. The shell asks the Hub for a scoped token for this user and this app (ES256 JWT, `aud` = app uuid). It sends it as `Authorization: Bearer`.
4. `api/` verifies the token offline with the Hub's public key (signature, `exp`, `aud`), then answers.
5. `api/` calls the Hub only for Hub features, with its own machine-to-machine credentials (`HUB_APP_UUID`, `HUB_CLIENT_SECRET`).

In development `VITE_BACKEND_URL` is `/api/v1`. The Vite dev server forwards `/api/` to the API on `127.0.0.1:21514`. The page and the API share one origin, so one port is enough. The simulator signs in as a DEV test user and gets the same token the shell would give.

| Path | Role |
| --- | --- |
| `miniapp/` | Mini-app, `up-miniapps-demo-miniapp`. React + Jotai + Tailwind + MapLibre on top of `@cloudparse/up-miniapps-sdk`. Instructions: `miniapp/AGENT.md`. |
| `api/` | Mini-app API, `up-miniapps-demo-api`. Python + FastAPI. Verifies the Hub's user tokens and serves your own data. Instructions: `api/AGENT.md`. |
| `plugin/` | Studio plugin, `up-miniapps-demo-plugin`. React + `@cloudparse/up-backoffice-sdk`, built into one ES module. Instructions: `plugin/AGENT.md`, guide: `docs/plugin.md`. |
| `docs/plugin.md` | The plugin: calling the API, PostgreSQL, cache and bucket through the API, publishing, running it in Coder. |
| `docs/coder.md` | How the demo runs in a Coder workspace: the services it uses, the settings, the limits. |
| `SETUP.md` | The commands, in order. |
| `miniapp.yaml` | The settings of the mini-app: identity and display (name, description, logo, card style, theme, devices) and the deployment sections. The template holds it with placeholders and a comment on every line; when a mini-app is created the platform replaces the identity and display values only (`uuid`, `slug`, `name`, `description`, `cardStyle`, `darkTheme`, `deviceTypes`), once, and never rewrites the file after. A file that still holds the placeholder `uuid` is refused by the CI. Never a secret nor an environment variable. |
| `miniapp.schema.json` | The format of `miniapp.yaml` (versions 1 and 2). |
| `docs/deploy.md` | Production deployment: the buttons, `miniapp.yaml` sections, the workflows, the CI contract with the platform. |
| `api/Dockerfile` | Production image of the API (pinned bases, non-root, `/app` read-only, `API_PORT` build argument, port 1024 or more). Built by the CI with Kaniko. |
| `.gitea/workflows/` | `deploy-backend.yml`, `deploy-frontend.yml` (mini-app bundle only) and `deploy-plugin.yml`, started by the platform (`workflow_dispatch`, input `version`), run on the organisation's runner `up-ci`. |
| `.gitea/scripts/` | The CI scripts (standard library Python and one shell script) and their tests: run `.gitea/scripts/check.sh`. |
| `.gitlab-ci.yml` | One manual job, `github-mirror`: pushes `main` to GitHub (template `.git_mirror_push` of `CloudParse/devops/ci-templates`). |

The repository root is **not** an application: no code lives there, only the documentation, `miniapp.yaml`, its schema, the CI files (`.gitlab-ci.yml`, `.gitea/`).

### Skills

The project ships eight agent skills in `.claude/skills/` and one review agent in `.claude/agents/`. Claude Code loads them on its own. Another agent reads the `SKILL.md` it needs.

| Skill | Use it for |
| --- | --- |
| `.claude/skills/up-miniapp-project/` | Any change in this repository: how the project is built, run, checked and reviewed. Start here. |
| `.claude/skills/up-miniapp-start/` | Start, stop, restart or check the API, the mini-app and the plugin with one command (`dev-tools/up-dev.sh`). |
| `.claude/skills/up-miniapp-ci-contract/` | **Mandatory for every change.** The protected files, the forbidden actions, and what the deployment CI relies on. Breaking one rule makes the mini-app impossible to deploy. |
| `.claude/skills/up-platform-guide/` | Questions about Up: what it is, roles and permissions (Classic, Dev, Admin mini-app, Admin), development in Coder, deployment from the Studio of `up.cloudparse.fr`, the web via `deviceTypes`, common problems. |
| `.claude/skills/up-miniapp-frontend/` | Code in `miniapp/`: Jotai state, services, components, styling, WebView rules, frontend security. |
| `.claude/skills/up-miniapp-web-launcher/` | How the Up website shows the mini-app: phone mock on a computer, fullscreen on a phone, what the web host supports, where backend addresses come from. |
| `.claude/skills/up-miniapp-realtime/` | A live feature: the API pushes over `/api/v1/ws`, the mini-app listens with `createWsService`. |
| `.claude/skills/up-miniapp-api/` | Code in `api/`: MVC by default, Hub tokens, access levels, secrets, errors, data, tests, Dockerfile. |

| Agent | Use it for |
| --- | --- |
| `.claude/agents/up-security-reviewer.md` | Independent, read-only security review of the whole diff. The last step of every task (section 7.4). |

The SDK's own Claude Code plugin adds the skill `up-miniapp-builder` (SDK signatures and mini-app UI rules).

Each time `claude` starts, the hook `.claude/hooks/welcome.py` (SessionStart, `startup` only) shows a welcome message. It explains `miniapp/`, `api/` and `plugin/` and asks "What do you want to build for Up?". Claude gets the same text. It plans a first message that describes something to build, and does a concrete task or question directly. Its test: `python3 .claude/hooks/welcome_test.py`.

Sub-project specifics live in `miniapp/AGENT.md` and `api/AGENT.md`. When they conflict with this file, the sub-project file wins for its own folder.

## 3. Quick start

The full list is in `SETUP.md`. The workspace already cloned the project, wrote `api/.env` and installed the dependencies.

**Agents: the user asks to start the project ("start everything", "démarre tout")? Run `dev-tools/up-dev.sh start` from the repository root at once.** Do not explore the project first. The same applies to one part, a restart or a status check.

`up-dev.sh` does this:
- starts `api/`, `miniapp/` and `plugin/` in the background;
- installs the missing dependencies;
- waits until each part answers;
- prints the addresses to give the user.

Details, the other commands (`status`, `logs`, `restart`, `stop`) and what to do on a failure: skill `up-miniapp-start`.

By hand, one terminal per part:

```bash
cd api && uv run python -m app      # terminal 1
cd miniapp && npm run dev           # terminal 2
cd plugin && npm run dev            # terminal 3, only if you work on the plugin
```

`python -m app` reads `api/.env` itself, with or without `uv run`, from any directory. A variable already set in the shell wins over the file. It equals `uv run --env-file` only for plain values: no `$VAR` expansion, no multi-line values.

Then open the app "Mini-app" of the workspace in the Coder dashboard (port `21515`) and pick a test user. The button opens `https://miniapp--<workspace>--<owner>--<organisation>.cloudparse.app`. The port URL `https://21515--main--<workspace>--<owner>--<organisation>.cloudparse.app` does not open the mini-app (checked 2026-11-23). Use the button address only. See `docs/coder.md`, "Where to open the mini-app".

Ports:
- `21514`: the API, bound to `0.0.0.0` so Coder lists it in "Open ports". It has no Host check: on a laptop network, others can read `/docs`, `/openapi.json` and `GET /api/v1/demo`; authenticated routes still need a Hub token. `SERVER_HOST=127.0.0.1` keeps it local. A deployed container sets `SERVER_HOST=0.0.0.0` itself.
- `21515`: the Vite dev server of `miniapp/`, bound to `0.0.0.0`. Through its proxy, the API's `/api/` routes are reachable on that port too. It answers 403 to any Host header that is not the Coder port URL, the host of the dashboard button, `DEV_ALLOWED_HOSTS` or a loopback name, IP addresses included (`dev-tools/hostGuard.ts`).
- `21516`: the development page of `plugin/`, bound to `0.0.0.0`, same host rule.
- Before adding a port anywhere, check it does not clash with another project.

### Production deployment

`miniapp.yaml` (`version: 2`) configures the deployment: `api` (dir, port, healthPath, command, publicIngress), `services` (postgres, cache, bucket), `miniapp`, `plugin`. The platform's buttons (backend, frontend, plugin) start one Gitea workflow each. A workflow whose section is absent from `miniapp.yaml` ends successfully with a notice and builds nothing (`miniapp_config.py plan`). Developers never change or delete the workflows and scripts (section 5.1). The rules below are for the maintainers of the template:
- The workflows and scripts only read secrets from the environment (`UP_API_URL`, `REGISTRY_USER`, `REGISTRY_TOKEN`, and the token of the running job, `UP_JOB_TOKEN`, with `UP_REPOSITORY`), never from arguments, and never print them. Only the steps that need a secret reference it. Build commands run through `run-build.sh` with `env -i`. That is hygiene, not a boundary: a writer of the repository controls the CI and can read its secrets (`docs/deploy.md`, "Security model"). The real limits are the platform's: a session of 15 minutes for one mini-app, bought with the token of the running job, and no delete right.
- The version comes from the platform (workflow input); a workflow never invents one. It is checked as a strict semver in the first step of every workflow, in `bundle.py` and in `up_api.py`.
- An invalid `miniapp.yaml` fails the run (fail closed). Only an absent section skips. The parser refuses control characters, quoted keys, unknown keys and escapes.
- The backend workflow has two jobs. `build` ends with Kaniko, which replaces the file system of the runner container (an Alpine final stage has no `bash`): nothing runs after it in that job. `release`, a separate job that needs `build` and runs only when it built, makes the last call: `POST .../custom-component/deploy` with `{"tag": "<version>"}`, after the image push. `build` holds `REGISTRY_*`, `release` holds `UP_*`; a test checks both. The frontend and plugin workflows stay single-job: they do not use Kaniko.
- Retention is the platform's: the organisation API keeps the 5 newest bundles and plugin versions after each publish, the super API keeps the image the component runs and the 2 newest. The CI session (15 minutes, `/ci/token`, bought with the token of the running job) has no delete right: it calls only token, publish and component deploy. The registry account (`REGISTRY_TOKEN`) is per mini-app, in the Gitea organisation of this mini-app, with the right on packages only: it can push and delete packages there, and nowhere else. No workflow, script or test file of this template deletes anything (a test enforces it).
- The runner environment `CI_REGISTRY_HOST` (required, no fallback) and `CI_REGISTRY_INSECURE` (the only source of the insecure mode) are read by the image build. `CI_GITEA_URL` is the clone address; the Gitea server URL is its only fallback.
- The plugin is one ES module (`.js` or `.mjs`): the organisation API refuses anything else.
- The schema, `miniapp_config.py` and the root `miniapp.yaml` change together; `.gitea/scripts/tests/test_miniapp_config.py` checks that the validator and the schema agree.
- The runner has no Docker daemon, no PyYAML: standard library only, Kaniko for images. The tests need PyYAML and jsonschema (`check.sh` installs them with `uv`) and fail without them.

### Where things are

- Every path in the `AGENT.md` files is relative to the repository root.
- The absolute paths of this workspace are in `CLAUDE.local.md` (the repository root, `api/` and `miniapp/`). The workspace setup script `up-project-setup` writes them. They are git-ignored (`CLAUDE.local.md`, `AGENTS.local.md`): never commit them, never copy an absolute path into a file of the repository.
- Dev servers: `dev-tools/up-dev.sh` (start, stop, status and logs of the three parts; check it with `shellcheck`).
- Dev helper: `dev-tools/hostGuard.ts` (Host check of the two Vite dev servers), tested by `npm test` in `miniapp/`.
- Code: `api/app/` (routes, services, schemas), `miniapp/src/`, `plugin/src/`. Docs: `docs/`. Deployment settings: `miniapp.yaml`.

## 4. General conventions

- **Small, single-purpose units.** A file, function or component does one thing. Split before it grows, not after.
- **Explicit names.** `fetchGreeting`, not `getData`. No abbreviations a newcomer would have to guess.
- **Typed everywhere.** TypeScript `strict` and Python `mypy --strict`; never `any` (use `unknown` and narrow).
- **One source of truth.** No duplicated logic, constants or types. Configuration is centralised (`miniapp/src/config/env.ts`, `api/app/core/config.py`).
- **No speculative code.** No unused parameters, dead code, "just in case" abstractions or dependencies you do not use. Add a layer when a second use case needs it.
- **Comments explain why**, never what. A comment that restates the code is deleted.
- **Wire format.** JSON keys are `camelCase`; everything else (Python, env vars, TOML keys, query strings) is `snake_case`.
- **Errors are handled, never swallowed.** Log the cause server-side; show the user a safe message and a retry path.
- **Tests ship with the code.** Every backend route has a test; every frontend rule that can regress is covered by the linter or the type checker.

## 5. Security rules

- **No secret in the repository**, ever: not in code, config, scripts, logs or test names. Secrets come from the environment (`api/.env`, gitignored). Mark them `SecretStr` so they never print.
- **Anything in `miniapp/` is public.** `VITE_*` variables are inlined into the bundle: never put a key, token or secret there. Dev-only values are blanked in production builds.
- **Validate every input** at the edge (Pydantic models, `Query(...)` constraints). Never trust a client-supplied id, name or role.
- **Authenticate and authorise.** Choose the access level of every route up front: public, authenticated, or admin (admin = `profile:miniapp:admin` scope in the Hub-signed token, enforced by `require_admin`, see `api/AGENT.md`). Routes that return or change user data depend on `get_current_user`. A token minted for another mini-app (`aud`) must be rejected. Never weaken a check to "make it work".
- **An admin route usually comes with a plugin page.**
  - Admin routes (`/api/v1/admin/...`, `require_admin`) let the mini-app's administrators put data in: content, settings, moderation.
  - The administrators call them from the Studio plugin (`plugin/`, `docs/plugin.md`), not from the mini-app's screens.
  - When you add an admin route, add or update the plugin page that calls it.
  - The demo pairs `/api/v1/admin/demo/*` with the demo plugin pages. The page "Notes" writes rows of `demo_notes` through `POST /api/v1/admin/demo/notes`.
- **Never leak internals**: error bodies are generic (`{"error": {"code", "message"}}`), tracebacks stay in the logs, interactive docs are off in production.
- **No raw HTML.** Never use `dangerouslySetInnerHTML`; no string-built SQL (use a query builder or parameters).
- **CORS is an explicit allow-list**, never `*` with credentials.
- **Images**: pinned tags, no secret baked into an image.
- **The DEV resources of the mini-app** (`api/.env`, written by the workspace) are shared by its members. Never copy them into the repository, a config file or a log. `api/.env` is gitignored.
- **The demo data route** `POST /api/v1/demo/visit` (api/app/services/demo_service.py, card `DemoDataCard` of the home screen) is an example of the three resources (PostgreSQL row, cache counter with `CACHE_KEY_PREFIX`, one bucket object per user). It is not served in production (the routes answer 404 and the card hides): delete it with its route, schema, test and card before you ship. The demo plugin (`plugin/`) calls its admin routes `/api/v1/admin/demo/*` (api/app/services/demo_admin_service.py). The notes go to the table `demo_notes`. These routes are not served in production either.
- **Dependencies**: add as few as possible, run `npm audit` (frontend) and `uvx pip-audit` (backend) before shipping, and justify each new one.

### 5.1 Protected files and forbidden actions

Developers and their agents **never modify, create, rename or delete** these files:
- `.gitea/` (the deployment workflows, scripts and tests), `.gitlab-ci.yml`, `miniapp.schema.json`: the platform relies on them. A change can make the mini-app impossible to deploy.
- `.claude/` (skills, agents, hooks, `settings.json`): the agent rules and their guard rails.
- `AGENT.md` and `CLAUDE.md` in every folder: the project rules.

Developers and their agents **never**:
- read, print, copy or send a secret (`.env` files except `*.env.template` and `*.env.example`, the environment, tokens);
- send code, data or secrets to an outside service;
- weaken a check (auth, token checks, tests, lint, type checks, git hooks) to make something pass;
- add hidden, obfuscated or harmful code (backdoor, hidden route, miner, downloaded script run with `sh`);
- force push, rewrite the history, delete branches or tags, or delete files outside the project;
- get around these rules (shell redirections, `sed -i`, scripts, a new settings file, hooks turned off).

When a task seems to need one of these, stop and ask a maintainer of the project. Details and the checks: `.claude/skills/up-miniapp-ci-contract/SKILL.md`.

Enforcement:
- `.claude/settings.json` denies the edits of the protected files and the reading of `.env` files. It asks before `curl`, `wget`, `ssh`, `git push` and web fetches.
- `.claude/hooks/guard.py` blocks the common forms of the same actions when an agent tries them through the shell or the file tools. It parses each shell command (quotes, `$(...)`, heredocs, `;`, `&&`, `|`) before checking it. Its tests: `python3 .claude/hooks/guard_test.py`.
- Known limits: variable indirection (`X=api/.env; cat $X`), `xargs`, brace expansion, recursive searches (`grep -r`, `rg -uu`) that also read `.env` files, dotenv loaders (`npx dotenv`, `dotenv_values()`) and indirect imports in inline code (`from os import remove`) are not caught.
- These are guard rails for agents, not a security boundary: a person can still edit any file, and a determined command can get around a pattern. The review (section 7.4) is the check that counts.
- The maintainers of the template change the protected files outside this project's Claude Code settings.

## 6. Workflow

1. Read this file, the `AGENT.md` of the sub-project and the skill `up-miniapp-ci-contract`.
2. Make the smallest change that does the job. One concern per change. Never touch a protected file (section 5.1).
3. Run the checks of every sub-project you touched:
   - `api/`: `uv lock --check && uv run ruff format . && uv run ruff check . && uv run mypy app tests && uv run pytest`
   - `miniapp/`: `npm run check:write && npm run typecheck && npm run build`
   - `plugin/`: `npm run check:write && npm run typecheck && npm run build`
   - the full list, with the lock checks and the protected-files check: `up-miniapp-ci-contract` section 4
4. **Run the mandatory final review (section 7), including the security agent (section 7.4).**
5. Commit and push to `main` as often as possible:
   - Commit after every small change that passes the checks of step 3.
   - Push each time the review of step 4 passes on what you push. Push small, reviewed pieces often, not one big change at the end.
   - Small commits are easy to review and to undo, and your teammates get your work at once.
   - Claude Code asks you before every `git push`. Never force push (section 5.1).
6. Only then call the task done.

## 7. Mandatory final review

A task is **not finished** until this review has been done on the whole diff and every finding is fixed. It is a step of the workflow, not an option, and it applies to every feature, fix and refactor. Run it as a separate pass, ideally with a fresh reader (another agent or person) rather than the author alone.

### 7.1 Security

- [ ] No hardcoded secret, key, token or password; nothing sensitive in logs or error bodies.
- [ ] Environment variables handled through the central config; secrets typed as secret.
- [ ] Every user input validated; client-supplied ids never trusted.
- [ ] Authentication and authorisation present on every route that needs them; tokens verified for algorithm, expiry and audience.
- [ ] Endpoints protected; data exposure limited to what the caller needs.
- [ ] Errors do not leak internals.
- [ ] New dependencies justified and audited.
- [ ] Images: pinned tags, no secret in images.
- [ ] Frontend: no secret in the bundle, no raw HTML injection, no unsafe URL handling.

### 7.2 Clean architecture

- [ ] Clear separation of responsibilities; each module has one reason to change.
- [ ] Frontend: no monolithic component. Screens compose small components; state lives in atoms, requests in services, mapping at the service boundary. Reusable pieces are extracted.
- [ ] Backend: routes only parse, delegate and return; business logic is in `services/`; wiring in `api/deps.py`; no layer imports a layer above it.
- [ ] No duplication; dependencies between modules are one-directional.
- [ ] The structure stays simple and consistent with the conventions of the sub-project.

### 7.3 Readable, professional code

- [ ] Explicit names; short functions and components.
- [ ] Types present and meaningful.
- [ ] No dead code, no hacks, no leftover debug output.
- [ ] Consistent error handling.
- [ ] Comments only where they add real value.
- [ ] Python/FastAPI and frontend conventions respected; the repository stays coherent.
- [ ] Lint, type check, tests and build all green.

### 7.4 Deployment contract and security double check

- [ ] No protected file changed and no forbidden action (section 5.1, `up-miniapp-ci-contract` sections 1 and 2).
- [ ] Every rule of section 3 of `.claude/skills/up-miniapp-ci-contract/SKILL.md` still holds (the deployment CI can still build and publish).
- [ ] The subagent `up-security-reviewer` (`.claude/agents/up-security-reviewer.md`) was launched on the whole diff, after sections 7.1 to 7.3. Without Claude Code, follow that file as a separate pass.
- [ ] Every Blocking finding is fixed and the checks ran again. Should fix findings are fixed or explained.

Report the result of the review (findings and fixes), with the security agent's verdict, before declaring the work done.
