# AGENT.md: Up Mini-App Template

Entry point for every agent and student working in this repository. Read it fully before changing anything, then read the `AGENT.md` of the sub-project you are touching.

Everything in this repository (code, comments, UI text, docs, commit messages) is written in English.

## 1. Purpose

This repository is a **reference template** for students building an Up mini-app: a small web app that runs inside the Up mobile app (the "shell"), plus the backend that serves it.

It is deliberately tiny: one backend route returns `Hello, World!` and the mini-app displays it. The point is not the feature but the **shape**: a clean architecture, a secure setup and a workflow you can copy for a real idea. The code must itself be an example of what we ask of you.

## 2. Architecture

```text
Up shell (phone)
   │  hosts the mini-app in a WebView; the SDK bridge talks to it
   ▼
up-miniapps-react-template        up-miniapps-template-python-backend        CloudParse backend ("Hub")
React + SDK  ──HTTP + user token──▶  FastAPI  ──machine-to-machine──▶  image cloudparse/up-backend
                                                                       + PostgreSQL, Redis, RustFS
```

| Path | Role |
| --- | --- |
| `up-miniapps-react-template/` | Frontend, `up-miniapps-react-template`. React + Jotai + Tailwind on top of `@cloudparse/up-miniapps-sdk`. Instructions: `up-miniapps-react-template/AGENT.md`. |
| `up-miniapps-template-python-backend/` | Mini-app backend, `up-miniapps-template-python-backend`. Python + FastAPI. Verifies the Hub's user tokens and serves your own data. Instructions: `up-miniapps-template-python-backend/AGENT.md`. |
| `docker-compose.yml` | Local environment: `postgres`, `redis`, `rustfs` and `cloudparse-backend` (image `cloudparse/up-backend`). It does **not** run your own two projects: they run on your machine so they hot-reload. |
| `scripts/` | `generate-keys.sh` (local signing keys) and `register-miniapp.sh` (registers your mini-app on the local Hub). |

The repository root is **not** an application: no code lives there, only the environment, the scripts and the documentation.

Sub-project specifics live in `up-miniapps-react-template/AGENT.md` and `up-miniapps-template-python-backend/AGENT.md`. When they conflict with this file, the sub-project file wins for its own folder.

## 3. Quick start

```bash
scripts/generate-keys.sh                 # once: local ES256 key pair (gitignored)
docker compose up -d                     # Hub + PostgreSQL + Redis + RustFS
scripts/register-miniapp.sh              # once: registers the app, writes up-miniapps-template-python-backend/.env

cd up-miniapps-template-python-backend && uv sync && uv run --env-file .env python -m app    # http://localhost:21514/docs
cd up-miniapps-react-template && npm install && cp .env.template .env && npm run dev # http://localhost:21515
```

Host ports (all on `127.0.0.1`, block 21509-21515): Hub `21509`, PostgreSQL `21510`, Redis `21511`, RustFS API `21512`, RustFS console `21513`, backend `21514`, mini-app `21515`. Override the compose ones through a root `.env` (see `.env.template`). Before adding a port anywhere, check it does not clash with another project.

## 4. General conventions

- **Small, single-purpose units.** A file, function or component does one thing. Split before it grows, not after.
- **Explicit names.** `fetchGreeting`, not `getData`. No abbreviations a newcomer would have to guess.
- **Typed everywhere.** TypeScript `strict` and Python `mypy --strict`; never `any` (use `unknown` and narrow).
- **One source of truth.** No duplicated logic, constants or types. Configuration is centralised (`up-miniapps-react-template/src/config/env.ts`, `up-miniapps-template-python-backend/app/core/config.py`).
- **No speculative code.** No unused parameters, dead code, "just in case" abstractions or dependencies you do not use. Add a layer when a second use case needs it.
- **Comments explain why**, never what. A comment that restates the code is deleted.
- **Wire format.** JSON keys are `camelCase`; everything else (Python, env vars, TOML keys, query strings) is `snake_case`.
- **Errors are handled, never swallowed.** Log the cause server-side; show the user a safe message and a retry path.
- **Tests ship with the code.** Every backend route has a test; every frontend rule that can regress is covered by the linter or the type checker.

## 5. Security rules

- **No secret in the repository**, ever: not in code, config, compose, scripts, logs or test names. Secrets come from the environment (`up-miniapps-template-python-backend/.env`, gitignored). Mark them `SecretStr` so they never print.
- **Anything in `up-miniapps-react-template/` is public.** `VITE_*` variables are inlined into the bundle: never put a key, token or secret there. Dev-only values are blanked in production builds.
- **Validate every input** at the edge (Pydantic models, `Query(...)` constraints). Never trust a client-supplied id, name or role.
- **Authenticate and authorise.** Choose the access level of every route up front: public, authenticated, or admin (admin = `profile:miniapp:admin` scope in the Hub-signed token, enforced by `require_admin`, see the backend `AGENT.md`). Routes that return or change user data depend on `get_current_user`. A token minted for another mini-app (`aud`) must be rejected. Never weaken a check to "make it work".
- **Never leak internals**: error bodies are generic (`{"error": {"code", "message"}}`), tracebacks stay in the logs, interactive docs are off in production.
- **No raw HTML.** Never use `dangerouslySetInnerHTML`; no string-built SQL (use a query builder or parameters).
- **CORS is an explicit allow-list**, never `*` with credentials.
- **Docker**: pinned image tags, ports bound to `127.0.0.1`, no secret baked into an image, keys mounted read-only. The local dev OTP bypass (`TESTING_ALLOW_DEV_AUTH_BYPASS`) exists for local use only and must never be enabled elsewhere.
- **Dependencies**: add as few as possible, run `npm audit` (frontend) and `uvx pip-audit` (backend) before shipping, and justify each new one.

## 6. Workflow

1. Read this file and the `AGENT.md` of the sub-project.
2. Make the smallest change that does the job. One concern per change.
3. Run the checks of every sub-project you touched:
   - `up-miniapps-template-python-backend/`: `uv run ruff format . && uv run ruff check . && uv run mypy app tests && uv run pytest`
   - `up-miniapps-react-template/`: `npm run check:write && npm run typecheck && npm run build`
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
- [ ] Docker and compose: pinned tags, local-only ports, no secret in images, safe inter-service communication.
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
