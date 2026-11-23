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
   │     ├─ /api/ ──proxy──▶ api/  FastAPI, 0.0.0.0:21514
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
- Vite answers only to hosts it knows. Coder sets `VSCODE_PROXY_URI` in the workspace: `miniapp/vite.config.ts` allows exactly two hosts (`plugin/vite.dev.config.ts` does the same with the button **Plugin**: `plugin--<workspace>--<owner>--<org>.<apps domain>`): the port URL of 21515 (`21515--<agent>--<workspace>--<owner>--<org>.<apps domain>`) and the link of the dashboard button "Mini-app" (`miniapp--<workspace>--<owner>--<org>.<apps domain>`). Another host needs the shell variable `DEV_ALLOWED_HOSTS` (comma separated; `.example.com` allows every subdomain).

- The Vite dev server (21515), the plugin's development page (21516, `docs/plugin.md`) and the API (21514) listen on `0.0.0.0`. Coder lists only the ports that listen on every interface in "Open ports". The two Vite servers answer 403 to any Host header that is not the Coder port URL, `DEV_ALLOWED_HOSTS` or a loopback name, IP addresses included (`dev-tools/hostGuard.ts`; Vite 8 alone lets IP Host headers through `allowedHosts`). The API (`api/configs/config.toml`, `server.host`) has no such check. On a laptop (shared Wi-Fi, a café), the API on `0.0.0.0` has no Host check: anyone on the network can read `/docs`, `/openapi.json`, `GET /api/v1/demo` and the public routes. Authenticated routes still need a Hub-signed token. Set `SERVER_HOST=127.0.0.1` to keep it local. A deployed container sets `SERVER_HOST=0.0.0.0` itself (`api/Dockerfile`), so production is unchanged.
- `api/.env` is read by `python -m app` itself (`api/app/core/dotenv.py`), with or without `uv run`. A variable already set in the shell wins over the file. `python -m app` gives the same result as `uv run --env-file` only for plain `KEY=VALUE` values (quotes, comments, `export`). Not supported: `$VAR` expansion and multi-line values. A skipped line is logged by its number, never by its value.

## When the workspace runs

- A workspace is created, and starts, when you click **Ouvrir mon workspace** in the Studio. Nothing runs before that click.
- Every **Ouvrir mon workspace** entry does the same: the button on the page of a mini-app, the link in the sidebar, the link on the home page, the "Coder" line of the services and the card of the components page.
- An entry that is not on a mini-app page uses your mini-apps. With one mini-app it opens that workspace. With several it shows a short list to choose from. With none it says "Aucune mini-app à ouvrir.".
- The first time, the button opens the Coder sign-in page. Sign in with the account you use in the Studio.
  - Right after your sign-in the platform creates the workspace and starts it. It takes about a minute. You do not click again.
  - Stay on the Studio tab: it asks every 5 seconds and says "Ton workspace est prêt" when the workspace exists. Click **Ouvrir mon workspace** to open it.
  - After the sign-in Coder shows the page of your workspace. If it says "Resource not found" in the first seconds, wait a few seconds and reload: the workspace is still being created.
  - The platform remembers your click for 30 minutes. After that, click again.
  - A person who never clicked never gets a workspace: nothing starts before a click.
  - Coder shows no warning.
- The next clicks open your workspace. If it was stopped, press **Start** in Coder.
- If the workspace page shows a failure, sign in to Coder if you have not yet, then press **Start**. A first build made before your first sign-in fails and the next click does not create a second workspace.
- A workspace that nobody used 5 minutes after its creation is stopped on its own, and one left running without use is stopped after 2 hours.
- A workspace created before 2026-11-23 can show the Coder warning "Ephemeral Parameters Detected" when you press Start. In Coder, open the workspace and press **Update** to get the current template: the warning is gone after it.
- A workspace stopped for a while keeps `/home/coder`: your files and installed tools are still there when it starts again.

## Your shell and the project settings

- The terminal of the workspace already has the project variables (`DATABASE_URL`, `CACHE_URL`, `STORAGE_*` and the others of the table above), the same names as in `api/.env`. `psql "$DATABASE_URL"` works in a new terminal.
- The workspace writes `CLAUDE.local.md` (and one per folder) at each start: the absolute paths, the commands and the ports of this workspace. Claude Code reads them. Git ignores them.
- The Coder buttons **Mini-app**, **API** and **Plugin** open in a new browser tab, so you can refresh the page.
- The DEV backend has no sign-in rate limit, because all the workspaces of an organisation share one address. A `429 Too Many Requests` on `/hub/api/v1/auth/login` in DEV means the organisation was deployed before this change: redeploy it from the super console.

## Coder says "Resource not found or you do not have access" (404)

- Coder keeps its own session in the browser. Signing out of the Studio does not sign out of Coder.
- After you change account in the Studio (Google, Apple, SMS, another developer), the Coder tab can still be signed in as the old account.
- Your workspace page then answers 404, because it belongs to the other account.
- Fix:
  1. In Coder, open the menu of your avatar (top right) and read which account is signed in.
  2. Sign out of Coder.
  3. Click "Ouvrir mon workspace" again in the Studio. Coder asks you to sign in: use the same account as in the Studio.
- The Studio shows the expected Coder user name under "Ouvrir mon workspace" (the part after `@` in the workspace address).
- Each account is a separate person for the platform: a developer role given to your Google account does not apply to your Apple or phone account.

## Where to open the mini-app (2026-11-20)

- The app "Mini-app": `https://miniapp--main--<workspace>--<owner>--<organisation>.cloudparse.app`.
- The forwarded port 21515: `https://21515--main--<workspace>--<owner>--<organisation>.cloudparse.app`.
- The app "API" (port 21514) and the app "Plugin" (port 21516, the development page of `plugin/`): same URL shape with `api--` and `plugin--`. The three buttons (Mini-app, API, Plugin) hide their ports from "Open ports". The Plugin button needs `npm run dev` running in `plugin/`.
- `cloudparse.app` is the apps domain of the production platform, shared by every organisation's Coder.
- Both open only for you, after the Coder sign-in. The app is owner-only. The port URL stays owner-only because the platform refuses port sharing (see Limits).

## Limits (2026-11-20)

- **The app URL is private.** It opens only for you, after the Coder sign-in. The platform blocks port sharing: Coder Community cannot limit a shared port to the organisation.
- **The mini-app runs in the SDK simulator** in your browser. The Up app on a phone does not load it. To see it as a member does on the website, publish a bundle and open the web launcher: [web-launcher.md](web-launcher.md).
- **The workspace is not production.** Production is deployed from the Studio: [deploy.md](deploy.md).
