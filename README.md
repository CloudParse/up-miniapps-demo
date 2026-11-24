# Up Mini-App Demo

A complete Up mini-app with its API: a React mini-app that uses every capability of `@cloudparse/up-miniapps-sdk` (`miniapp/`), a FastAPI API (`api/`) and the Studio plugin of the mini-app (`plugin/`, [`docs/plugin.md`](docs/plugin.md)). Every mini-app project of an organisation starts as a copy of it. It runs in the project's Coder workspace, against the organisation's DEV backend and the mini-app's own DEV database, cache and bucket.

Guides by folder, for beginners (install, run, ports, tests, Docker, deploy, common errors): [`api/README.md`](api/README.md), [`miniapp/README.md`](miniapp/README.md), [`plugin/README.md`](plugin/README.md).

Run the commands in [`SETUP.md`](SETUP.md) to get started, then read [`AGENT.md`](AGENT.md): it holds the architecture, the quick start, the conventions and the review checklist. Then read `miniapp/AGENT.md` and `api/AGENT.md`.

## Environment variables (the same names in the Coder workspace and in production)

The code reads the same names everywhere, so nothing changes between your workspace and a deployed component. Never put a value in the repository (`api/.env` is ignored by git, production secrets stay in Vault).

| Variable | In your Coder workspace (DEV) | In production (the deployed component) |
| --- | --- | --- |
| `DATABASE_URL` | `api/.env`, written by `up-project-setup`: PostgreSQL `up_dev_<mini-app>` | set by the platform: your mini-app's own PostgreSQL database and role (`services.postgres: true` in `miniapp.yaml`) |
| `CACHE_URL`, `CACHE_KEY_PREFIX` | `api/.env`: DEV Valkey, every key starts with the prefix | set by the platform (`services.cache: true`) |
| `STORAGE_ENDPOINT`, `STORAGE_ACCESS_KEY`, `STORAGE_SECRET_KEY`, `STORAGE_BUCKET` | `api/.env`: DEV bucket `up-dev-<mini-app>` | set by the platform (`services.bucket: true`); `STORAGE_ENDPOINT` is `host:port` there, a URL in the workspace: `api/app/core/config.py` accepts both |
| `HUB_PUBLIC_KEY_PATH` | `api/.env`: the DEV backend's public key | mounted by the platform (`/etc/up-platform/jwt/public.pem`) |
| `HUB_APP_UUID`, `HUB_CLIENT_SECRET` | not set: the DEV defaults of `api/configs/config.toml` (shared mock registration) | set by the platform (the real identity of your mini-app); the API refuses to start in production on the DEV defaults |
| `MINIAPP_UUID`, `MINIAPP_SLUG`, `ORGANIZATION_SLUG` | not set | set by the platform |

How: a Coder workspace gets `api/.env` at each start (`docs/coder.md`), a deployed component gets its variables from the platform (`docs/deploy.md`). Only the members of the mini-app and the admins of the organisation get the DEV values. `GET /api/v1/resources` (signed in) tells whether the database, the cache and the bucket answer, in both places.

How it runs in Coder: [`docs/coder.md`](docs/coder.md).

How the Studio plugin works, how it reaches the API, the database, the cache and the bucket, how it is published and run in development: [`docs/plugin.md`](docs/plugin.md).

How it goes to production (buttons in the platform for the backend, the frontend and the plugin, Gitea CI, everything configured in `miniapp.yaml`): [`docs/deploy.md`](docs/deploy.md).

The settings of the mini-app (name, description, logo, card style, theme, devices) live in `miniapp.yaml` at the root of each project repository, written by the platform whenever it is missing (never overwritten); [`miniapp.schema.json`](miniapp.schema.json) describes the format. See `SETUP.md`, "Settings of the mini-app".

Agent skills (Claude Code loads them on its own): `.claude/skills/`. The list is in `AGENT.md`, section "Skills".

**Before you ship:** delete the demo of the DEV resources (`api/app/services/demo_service.py`, its route `api/app/api/routes/demo.py`, schema, test, and the card `miniapp/src/features/home/DemoDataCard.tsx`; with `api/app/services/demo_admin_service.py`, the plugin page `plugin/src/features/demo/` and its service). It is an example; the API does not serve it in production.

## Features covered (last audit: 2026-11-24)

What this template shows, and where. When the platform or the SDK gets a feature, add a line here and change the audit date.

| Area | Covered | Where |
| --- | --- | --- |
| SDK | `@cloudparse/up-miniapps-sdk` 0.17.0 pinned. Boot (`initialize`, context, insets), user profile, `createApiService`, `createWsService` (broadcast), storage and secure storage, permissions, haptics, location, map and routing, journey, QR scan and generation, media, payment, fidelity, achievements, network, system UI and exit | `miniapp/src/` (`features/`, `services/`) |
| Backend addresses | Given by the platform only: `window.__UP_BACKEND_URLS__`, `env`, `UPDATE_CONTEXT` when the backend is registered later. Never in the code | `docs/web-launcher.md`, `miniapp/src/services/backend.ts` |
| Web launcher | Phone mock and device picker on a computer, fullscreen on a phone or in a narrow window (with a **Plein écran** button where the browser allows it), install on the home screen, web host limits with a clear message | `docs/web-launcher.md`, `miniapp/src/lib/errors.ts` |
| Realtime | WebSocket route `/api/v1/ws`, hub, push example, listening client, **Ping / pong button with the round trip**, works in development behind a Coder URL (Vite proxy with `ws: true`, same-site Origin), demo routes only in development (a production build calls none), tests | `docs/realtime.md`, `api/app/api/routes/realtime.py` |
| API | FastAPI, access levels (public, user, admin), Hub tokens and the admin scope, `.env` loader, Host guard, `0.0.0.0` dev servers, database, cache, bucket, tests | `api/`, `api/AGENT.md` |
| Studio plugin | Boilerplate in light mode with the Studio palette and fonts (backoffice SDK 0.3.1), development page, admin routes | `plugin/`, `docs/plugin.md` |
| Coder | Workspace created by the person's click on "Ouvrir mon workspace" (no pod before), project variables in the shell, `CLAUDE.local.md`, ports, buttons that open a tab, no sign-in rate limit in DEV | `docs/coder.md`, `SETUP.md` |
| Deploy | `miniapp.yaml`, buttons in the Studio, Gitea CI, addresses registered by the platform, `publicIngress` | `docs/deploy.md`, `miniapp.yaml` |
| Agent skills | Project, CI contract, platform guide, frontend, API, web launcher, realtime (draft), security reviewer. Welcome message at each `claude` start (`miniapp/`, `api/`, `plugin/`, "What do you want to build for Up?") | `.claude/skills/`, `.claude/agents/` |

## Dependency versions (last audit: 2026-11-23)

Locked versions at the audit. Every package is at its latest release, except the held-back ones below the table.

| Part | Package | Version |
| --- | --- | --- |
| miniapp | `@cloudparse/up-miniapps-sdk` | 0.17.0 (latest published) |
| miniapp | react, react-dom | 19.3.1 |
| miniapp | vite, tailwindcss, typescript | 8.3.8, 4.3.5, 7.0.2 |
| miniapp | maplibre-gl, jotai, lucide-react, biome | 6.19.0, 3.0.2, 1.78.0, 2.6.8 |
| plugin | `@cloudparse/up-backoffice-sdk` | 0.3.1 (latest published) |
| plugin | react, vite, typescript | 19.3.1, 8.3.8, 7.0.2 |
| api | python, uv (Docker image) | 3.14.10 slim trixie, 0.13.9 (both latest) |
| api | fastapi, uvicorn, pydantic, pyjwt, redis, boto3, psycopg | 0.165.0, 0.54.0, 2.14.4, 2.15.1, 8.2.0, 1.44.9, 3.3.9 |
| api | ruff, mypy, pytest | 0.17.6, 2.4.1, 9.2.0 |
| CI | `CloudParse/devops/ci-templates` | v2.5.0 |

Held back: nothing. `npm outdated` still lists `@cloudparse/up-miniapps-sdk` "latest 0.2.3" and `@cloudparse/up-backoffice-sdk` "latest 0.1.1": npm sorts old dist-tags, the real latest releases are the versions in the table (`npm view <package> version`).

Not covered on purpose: a private WebSocket channel with tickets (described in `docs/realtime.md`), several API replicas, payments with a real provider.
