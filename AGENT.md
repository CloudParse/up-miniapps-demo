# AGENT.md: Up Mini-App Demo

Entry point for every agent and student working in this repository. Read it fully before changing anything, then read the `AGENT.md` of the sub-project you are touching.

Code, comments, docs and commit messages are written in English. The UI text of `miniapp/` is French.

## 1. Purpose

This repository is the **demo project** for teams building an Up mini-app: a web app that runs inside the Up mobile app (the "shell"), plus the API that serves it. Every mini-app project of an organisation starts as a copy of it (its own repository on the organisation's Gitea, its own Coder workspace per member).

- `miniapp/` uses every public capability of `@cloudparse/up-miniapps-sdk` (map and journeys, QR codes, network, realtime, storage, haptics, permissions, account, achievements, payment demo). Its home screen shows the message of the backend route `GET /api/v1/hello`.
- `api/` is a small FastAPI service with public, authenticated and admin routes, wired to the mini-app's own DEV database, cache and bucket.

The point is the **shape**: a clean architecture, a secure setup and a workflow you can copy for a real idea. The code must itself be an example of what we ask of you.

Where it lives:
- GitLab `CloudParse/up/miniapps/up-miniapps-demo` is the source.
- The manual CI job `github-mirror` (`.gitlab-ci.yml`) pushes `main` to the public GitHub mirror `CloudParse/up-miniapps-demo`.

## 2. Architecture

The project runs in its **Coder workspace** (`docs/coder.md`). The API and the mini-app both run in the workspace. They use the organisation's DEV environment: its backend (the "Hub", with test users) and the mini-app's own database, cache and bucket.

```text
Browser ──Coder app "Mini-app" (private)──▶ miniapp/ (Vite, 21515) ──/api/ proxy──▶ api/ (FastAPI, 127.0.0.1:21514)
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
| `docs/coder.md` | How the demo runs in a Coder workspace: the services it uses, the settings, the limits. |
| `SETUP.md` | The commands, in order. |
| `miniapp.yaml` | In a project repository only (written by the platform whenever it is missing, never overwritten; not in this template): the backoffice settings of the mini-app (name, description, logo, card style, theme, devices). Never a secret nor an environment variable. |
| `miniapp.schema.json` | The format of `miniapp.yaml`. |
| `.gitlab-ci.yml` | One manual job, `github-mirror`: pushes `main` to GitHub (template `.git_mirror_push` of `CloudParse/devops/ci-templates`). |

The repository root is **not** an application: no code lives there, only the documentation, `miniapp.yaml`, its schema and the CI file.

Sub-project specifics live in `miniapp/AGENT.md` and `api/AGENT.md`. When they conflict with this file, the sub-project file wins for its own folder.

## 3. Quick start

The full list is in `SETUP.md`. The workspace already cloned the project, wrote `api/.env` and installed the dependencies. In short:

```bash
cd api && uv run --env-file .env python -m app    # terminal 1
cd miniapp && npm run dev                         # terminal 2
```

Then open the app "Mini-app" of the workspace in the Coder dashboard (port `21515`) and pick a test user.

Ports:
- `21514`: the API, bound to `127.0.0.1`.
- `21515`: the Vite dev server, bound to `127.0.0.1` (Coder reaches it there). Through its proxy, the API's `/api/` routes are reachable on that port too.
- Before adding a port anywhere, check it does not clash with another project.

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
- **Never leak internals**: error bodies are generic (`{"error": {"code", "message"}}`), tracebacks stay in the logs, interactive docs are off in production.
- **No raw HTML.** Never use `dangerouslySetInnerHTML`; no string-built SQL (use a query builder or parameters).
- **CORS is an explicit allow-list**, never `*` with credentials.
- **Images**: pinned tags, no secret baked into an image.
- **The DEV resources of the mini-app** (`api/.env`, written by the workspace) are shared by its members. Never copy them into the repository, a config file or a log. `api/.env` is gitignored.
- **Dependencies**: add as few as possible, run `npm audit` (frontend) and `uvx pip-audit` (backend) before shipping, and justify each new one.

## 6. Workflow

1. Read this file and the `AGENT.md` of the sub-project.
2. Make the smallest change that does the job. One concern per change.
3. Run the checks of every sub-project you touched:
   - `api/`: `uv run ruff format . && uv run ruff check . && uv run mypy app tests && uv run pytest`
   - `miniapp/`: `npm run check:write && npm run typecheck && npm run build`
4. **Run the mandatory final review (section 7).**
5. Only then call the task done.

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

Report the result of the review (findings and fixes) before declaring the work done.
