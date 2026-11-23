---
name: up-miniapp-project
description: Start here for any change in this Up mini-app project. Where things run, the settings file miniapp.yaml, deployment, test users, how to add a feature, the checks and the mandatory review. Points to the mandatory skill up-miniapp-ci-contract (protected files, forbidden actions, CI rules), the security agent up-security-reviewer, and the deeper skills up-platform-guide, up-miniapp-frontend and up-miniapp-api.
---

# Up mini-app project

Read first:
1. `AGENT.md` at the root.
2. The `AGENT.md` of the folder you change: `api/` or `miniapp/`.

Those files are the rules. This skill is the short path through them.

Deeper skills of this repository:
- `up-miniapp-ci-contract`: **mandatory for every change**. What the deployment CI relies on and must never change.
- `up-platform-guide`: questions about Up, roles, development, deployment, the web.
- `up-miniapp-frontend`: code in `miniapp/`.
- `up-miniapp-api`: code in `api/`.
- `up-miniapp-web-launcher`: the website display, the web host limits, the backend addresses.
- `up-miniapp-realtime`: a live feature over the WebSocket.

## Where things run

- The project runs in its Coder workspace.
- At each start, the workspace writes `api/.env` (gitignored). It holds `DATABASE_URL`, `CACHE_URL`, `CACHE_KEY_PREFIX`, `STORAGE_ENDPOINT`, `STORAGE_ACCESS_KEY`, `STORAGE_SECRET_KEY`, `STORAGE_BUCKET` and `HUB_PUBLIC_KEY_PATH`.
- Never print, log or commit those values.

Start:
1. `cd api && uv run --env-file .env python -m app`. The API listens on 127.0.0.1:21514.
2. `cd miniapp && npm run dev`. Vite listens on 21515 and sends `/api/` to the API.
3. Open the workspace app "Mini-app", or the forwarded port: `https://21515--main--<workspace>--<owner>--<organisation>.cloudparse.app` (private, after the Coder sign-in).

`GET /api/v1/resources` (signed in) tells whether the database, the cache and the bucket answer.

## Settings of the mini-app (`miniapp.yaml`)

- `miniapp.yaml` sits at the root. This template holds it with placeholders. Its format is `miniapp.schema.json`.
- The platform writes it when it is missing. It never overwrites it.
- Identity fields: `uuid` and `slug`. Never change them.
- Display fields: `name`, `description`, `logo` (a `.webp` of the repository, or `null`), `cardStyle`, `darkTheme`, `deviceTypes`.
- CI does not apply the display fields yet (2026-11-20). The Studio value is the one used. Change it in the Studio too, and keep both equal.
- `version: 2` adds the deployment sections. The platform reads them at each deploy.
  - `api`: `dir`, `port` (1024 or more), `healthPath`, `command`, `publicIngress`.
  - `services`: `postgres`, `cache`, `bucket`.
  - `miniapp`: `dir`, `build`, `out`.
  - `plugin`: `dir`, `build`, `out`, `file` (one `.js` or `.mjs` module).
- Example: the `miniapp.yaml` of the project root (placeholders and a comment on every line; the platform fills the identity values when the mini-app is created).
- Never put a secret or an environment variable in it.

## Deploying

- An admin of the organisation presses the Studio buttons "Déployer le backend", "Déployer le frontend" and "Déployer le plugin".
- Each button starts one workflow of `.gitea/workflows/`: `deploy-backend.yml`, `deploy-frontend.yml`, `deploy-plugin.yml`. They run on the organisation's runner.
- The backend workflow builds `api/Dockerfile` with the port `api.port`.
- The frontend workflow publishes the `index.base64.gz` of `up-sdk build` as `miniapp-<version>.base64.gz`.
- The plugin workflow publishes the plugin module.
- A workflow whose section is missing from `miniapp.yaml` does nothing and ends green. Never change or delete a workflow (`AGENT.md` section 5.1).
- The platform picks the version: patch + 1.
- Never change `.gitea/`: only the maintainers of the template do.
- Details: `docs/deploy.md`.

## Users and tokens in development

- The DEV backend has 15 test users (`miniapp/src/dev/devHub.ts`).
- The simulator signs in as the user picked. It sends a real scoped token, so `get_current_user` works as in production.
- Every mini-app shares the DEV registration `0d0d0d0d-0000-4000-8000-000000000001` / `mock_secret`. These two values are the defaults of `api/configs/config.toml`.
- Never write real values in that file. Production sets `HUB_APP_UUID` and `HUB_CLIENT_SECRET` in the environment.

## Adding a feature

1. API (MVC, see `up-miniapp-api`). Pick the access level first: public, authenticated (`CurrentUserDep`) or admin (`require_admin`). Then:
   - schema in `api/app/schemas/`;
   - logic in `api/app/services/`;
   - provider in `api/app/api/deps.py`;
   - route in `api/app/api/routes/`;
   - mount the router in `api/app/api/router.py`;
   - one test per route.
2. Data:
   - PostgreSQL through `config.database.url`. Parameters only, never string-built SQL.
   - Cache: every key and channel starts with `config.cache.key_prefix`. The cache user can touch nothing else and cannot `SCAN` or `KEYS`.
   - Bucket: `config.storage.bucket` only.
3. Mini-app (see `up-miniapp-frontend`). UI text is French. Code is English. Then:
   - one service per resource in `miniapp/src/services/`, through the SDK client;
   - state in `miniapp/src/atoms/`;
   - screens in `miniapp/src/features/`.
4. A new setting: key in `api/configs/config.toml`, field in `api/app/core/config.py`, test in `api/tests/test_config.py`.

## Checks, then the review

```bash
# from the repository root
(cd api && uv lock --check && uv run ruff format . && uv run ruff check . && uv run mypy app tests && uv run pytest)
(cd miniapp && npm run check:write && npm run typecheck && npm run build)
```

Then:
1. Run the mandatory final review of `AGENT.md` section 7 on the whole diff.
2. Check the frozen items of `up-miniapp-ci-contract`.
3. Launch the subagent `up-security-reviewer` on the whole diff (security double check).
4. Fix every finding. Report both reviews.
5. Commit with your own Gitea account. The repository belongs to the mini-app.
