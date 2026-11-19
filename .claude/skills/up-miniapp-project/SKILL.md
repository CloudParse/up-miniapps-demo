---
name: up-miniapp-project
description: How this Up mini-app project is built and run in its Coder workspace - api/ (FastAPI) and miniapp/ (React + SDK), the mini-app's own DEV database, cache and bucket, the DEV backend's test users, the checks and the review. Use for any change in this repository, before writing code. For SDK signatures and mini-app UI rules, use the up-miniapp-builder skill of the SDK plugin.
---

# Up mini-app project

Read `AGENT.md` at the root, then the `AGENT.md` of the folder you change (`api/` or `miniapp/`). They are the rules; this skill is the short path through them.

## Where things run

- The project runs in its Coder workspace. `api/.env` (gitignored) is written at each start: `DATABASE_URL`, `CACHE_URL`, `CACHE_KEY_PREFIX`, `STORAGE_ENDPOINT`, `STORAGE_ACCESS_KEY`, `STORAGE_SECRET_KEY`, `STORAGE_BUCKET`, `HUB_PUBLIC_KEY_PATH`. Never print, log or commit their values.
- Start: `cd api && uv run --env-file .env python -m app` (127.0.0.1:21514), then `cd miniapp && npm run dev` (21515, proxies `/api/` to the API). Open the workspace app "Mini-app".
- `GET /api/v1/resources` (signed in) tells whether the database, the cache and the bucket answer.

## Settings of the mini-app

- `miniapp.yaml` (repository root) holds the backoffice settings: `uuid`, `slug` (both never change), `name`, `description`, `logo` (a `.webp` of the repository or `null`), `cardStyle`, `darkTheme`, `deviceTypes`. Its format is `miniapp.schema.json`.
- Edit it to change how the mini-app looks; never add a secret or an environment variable to it. The backoffice is updated from it by a CI job (not available yet).

## Users and tokens in development

- The DEV backend has 15 test users (`miniapp/src/dev/devHub.ts`). The simulator signs in as the one picked and sends a real scoped token, so `get_current_user` works as in production.
- Every mini-app shares the DEV registration `0d0d0d0d-0000-4000-8000-000000000001` / `mock_secret` (defaults of `api/configs/config.toml`). Never replace them by real values in the file: production sets `HUB_APP_UUID` and `HUB_CLIENT_SECRET` in the environment.

## Adding a feature

1. API: schema in `api/app/schemas/`, logic in `api/app/services/`, route in `api/app/api/routes/`, provider in `api/app/api/deps.py`, a test per route. Choose public, authenticated (`CurrentUserDep`) or admin (`require_admin`) up front.
2. Data: PostgreSQL through `config.database.url` (parameters, never string-built SQL). Cache: every key and channel starts with `config.cache.key_prefix` (the cache user can touch nothing else and cannot `SCAN`). Bucket: `config.storage.bucket` only.
3. Mini-app: a service per resource in `miniapp/src/services/` through the SDK client, state in `miniapp/src/atoms/`, screens in `miniapp/src/features/`. UI text in French, code in English.
4. A new setting: key in `api/configs/config.toml`, field in `api/app/core/config.py`, test in `api/tests/test_config.py`.

## Checks, then the review

```bash
cd api && uv run ruff format . && uv run ruff check . && uv run mypy app tests && uv run pytest
cd miniapp && npm run check:write && npm run typecheck && npm run build
```

Then run the mandatory final review of `AGENT.md` section 7 on the whole diff, fix every finding, and report it. Commit with your own Gitea account; the repository is the mini-app's own.
