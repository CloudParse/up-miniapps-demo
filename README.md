# Up Mini-App Demo

A complete Up mini-app with its API: a React mini-app that uses every capability of `@cloudparse/up-miniapps-sdk` (`miniapp/`), a FastAPI API (`api/`) and the Studio plugin of the mini-app (`plugin/`, [`docs/plugin.md`](docs/plugin.md)). Every mini-app project of an organisation starts as a copy of it. It runs in the project's Coder workspace, against the organisation's DEV backend and the mini-app's own DEV database, cache and bucket.

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
