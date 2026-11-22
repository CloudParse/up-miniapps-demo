# How the project runs in a Coder workspace

Your organisation's Coder (`https://coder.<organisation>.<domain>`) gives you one workspace per mini-app you are a member of. It is a remote Linux machine with VS Code in the browser, a terminal and Claude Code. `SETUP.md` lists the commands.

## The big picture

The mini-app and its API both run **in your workspace**. They use your organisation's **DEV environment** (namespace `dev-<organisation>`), never PROD.

```text
Your browser
   │  app "Mini-app" or port 21515 on *--<organisation>.cloudparse.app (private: only you, after the Coder sign-in)
   ▼
Coder workspace (dev-<organisation>)
   ├─ miniapp/  Vite dev server, port 21515, live reload, SDK simulator
   │     ├─ /api/ ──proxy──▶ api/  FastAPI, 127.0.0.1:21514
   │     │                      ├──▶ DEV backend (the Hub)          http://backend-service:8080/api/v1
   │     │                      ├──▶ your mini-app's DEV database  DATABASE_URL
   │     │                      ├──▶ your mini-app's DEV cache     CACHE_URL, CACHE_KEY_PREFIX
   │     │                      └──▶ your mini-app's DEV bucket    STORAGE_*
   │     └─ /hub/ ──proxy──▶ DEV backend: sign in as a test user (development only)
   └─ VS Code, terminal, Claude Code
```

## Your mini-app's DEV resources

`up-project-setup` writes them to `api/.env` at each start of the workspace, under the names a deployed component gets, so the code does not change between the workspace and production:

| Variable | What |
| --- | --- |
| `DATABASE_URL` | PostgreSQL database `up_dev_<mini-app>`, owned by your mini-app's own role |
| `CACHE_URL`, `CACHE_KEY_PREFIX` | Valkey (Redis protocol). Every key and channel must start with `CACHE_KEY_PREFIX`: the cache user can touch nothing else, and cannot list keys (`SCAN`, `KEYS` are refused) |
| `STORAGE_ENDPOINT`, `STORAGE_ACCESS_KEY`, `STORAGE_SECRET_KEY`, `STORAGE_BUCKET` | S3 bucket `up-dev-<mini-app>`, your mini-app's only |
| `HUB_PUBLIC_KEY_PATH` | the DEV backend's public key, to verify the test users' tokens |

- Only the members of the mini-app and the admins of the organisation get them: Vault checks your Coder sign-in against the mini-app's members and the organisation's admins (they can read these passwords in the Vault UI anyway). A super user does not.
- They belong to the mini-app, not to you: every member of the mini-app shares the same database, cache and bucket.
- `GET /api/v1/resources` (signed in) tells whether each one answers. `POST /api/v1/demo/visit` (signed in, and the "Enregistrer une visite" card of the mini-app) writes one row in the database, one counter in the cache and one object in the bucket, then reads them back: the quickest proof that the three resources work from the mini-app. The demo is an example: it is NOT served when `environment` is `production` (404, the card hides itself), the table `demo_visits` is created once at startup by the DEV role, which owns its own database, and the object of each user is `demo/<user id>.json`. Delete `api/app/services/demo_service.py`, its route, schema, test and the card `miniapp/src/features/home/DemoDataCard.tsx` before you ship.
- The same variable names are set by the platform on a deployed component, so the code does not change. One difference: `STORAGE_ENDPOINT` is `host:port` there and a URL here; `api/app/core/config.py` adds `http://` when the scheme is missing.
- When the mini-app is deleted, they are deleted with it, and so is this workspace.

## The DEV backend and its test users

- The DEV backend runs in development mode, with test data only. Its tokens are worthless in production.
- Every mini-app uses the same registration there: `hub.app_uuid` `0d0d0d0d-0000-4000-8000-000000000001`, `hub.client_secret` `mock_secret` (the defaults of `api/configs/config.toml`). They are not secrets: they open nothing outside the DEV backend.
- 15 test users exist (`miniapp/src/dev/devHub.ts` lists them). The simulator signs in as the one you pick and gets the same 5-minute token the Up app would give your mini-app, renewed every 4 minutes. Change user on the "Mon compte" tab.

## What the workspace gives you

- Python 3.14 and `uv`, Node.js 26 LTS, Go, git, Claude Code (`claude`) and VS Code in the browser.
- No Docker daemon. No root: you are `uid 1000`.
- Over the network: the organisation's coderd, its DEV backend, DEV PostgreSQL, DEV cache and DEV bucket, its Gitea and Vault, plus DNS and the internet. No Kubernetes API.
- Only `/home/coder` survives a restart. Keep the project and every tool you install there.
- Git: the repository's remote is your organisation's Gitea, with your own account (Coder asks you to connect it once).

## Settings that make it work

- `miniapp/.env` keeps `VITE_BACKEND_URL=/api/v1`. Vite forwards `/api/` to the API on `127.0.0.1:21514`, and `/hub/` to the DEV backend (`DEV_HUB_ORIGIN`, default `http://backend-service:8080`).
- Vite answers only to hosts it knows. Coder sets `VSCODE_PROXY_URI` in the workspace: `miniapp/vite.config.ts` allows exactly two hosts: the port URL of 21515 (`21515--<agent>--<workspace>--<owner>--<org>.<apps domain>`) and the link of the dashboard button "Mini-app" (`miniapp--<workspace>--<owner>--<org>.<apps domain>`). Another host needs the shell variable `DEV_ALLOWED_HOSTS` (comma separated; `.example.com` allows every subdomain).

## Where to open the mini-app (2026-11-20)

- The app "Mini-app": `https://miniapp--main--<workspace>--<owner>--<organisation>.cloudparse.app`.
- The forwarded port 21515: `https://21515--main--<workspace>--<owner>--<organisation>.cloudparse.app`.
- `cloudparse.app` is the apps domain of the production platform, shared by every organisation's Coder.
- Both open only for you, after the Coder sign-in. The app is owner-only. The port URL stays owner-only because the platform refuses port sharing (see Limits).

## Limits (2026-11-20)

- **The app URL is private.** It opens only for you, after the Coder sign-in. The platform blocks port sharing: Coder Community cannot limit a shared port to the organisation.
- **The mini-app runs in the SDK simulator** in your browser. The Up app on a phone does not load it.
- **The workspace is not production.** Production is deployed from the Studio: [deploy.md](deploy.md).
