# How the demo runs in a Coder workspace

Your organisation's Coder (`https://coder.<slug>.<domain>`) gives you a workspace. It is a remote Linux machine with VS Code in the browser, a terminal and Claude Code. The demo is made to run there. This page explains how it works. `SETUP.md` lists the commands.

## The big picture

Your mini-app backend and your mini-app frontend both run **in your workspace**. They use the services of your organisation's **DEV environment** (namespace `dev-<slug>`), never PROD.

```text
Your browser
   │  https://21515--main--<workspace>--<you>--<slug>.<apps domain>   (private: only you, after the Coder sign-in)
   ▼
Coder workspace (dev-<slug>)
   ├─ frontend/  Vite dev server, port 21515, live reload
   │     └─ /api/ ──proxy──▶ backend/  FastAPI, 127.0.0.1:21514
   │                            ├──▶ DEV backend of the organisation (the Hub)   http://backend:8080/api/v1
   │                            ├──▶ DEV PostgreSQL                              DATABASE_URL, PG*
   │                            └──▶ DEV bucket (S3, RustFS)                     S3_ENDPOINT, AWS_*
   └─ VS Code, terminal, Claude Code
```

- **Frontend** (`frontend/`): the Vite dev server on port 21515. Open its Coder port URL to see your changes live in the SDK simulator. Every save reloads the page.
- **Backend** (`backend/`): FastAPI on `127.0.0.1:21514`. The frontend reaches it through the Vite proxy (`/api/`), so you only ever open port 21515.
- **DEV backend of the organisation** (the Hub): it signs your users' tokens. Your backend calls it for Hub features. The default `hub.base_url` in `backend/configs/config.toml` is `http://backend:8080/api/v1`.
- **DEV PostgreSQL and DEV bucket**: meant to be reached with your **own** short-lived credentials (next section). On 2026-11-18 PostgreSQL needs the workaround in "Limits", and the bucket gets no keys. The demo code does not use them yet.

## What the workspace gives you (2026-11-18)

- No Docker daemon. No root: you are `uid 1000`.
- No access to the Kubernetes API. Over the network, the workspace reaches only its organisation's coderd, DEV backend, DEV PostgreSQL, DEV bucket, Gitea and Vault, plus DNS and the internet.
- Installed: git, Node.js 26 LTS, Go, Claude Code (`claude`) and VS Code in the browser.
- Not installed: Python and `uv`. `SETUP.md` step 1 installs uv.
- Only `/home/coder` survives a restart. Keep the project and every tool you install there.
- Personal data credentials. At each start, `up-org-credentials` writes them into `~/.config/up/env`, and every shell loads that file:
  - PostgreSQL: `DATABASE_URL`, `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD`. Vault creates a personal account for you, valid 8 hours.
  - Bucket: `S3_ENDPOINT`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`, `AWS_REGION`. Temporary keys, valid 8 hours. Not written on 2026-11-18 (see "Limits").
  - PostgreSQL rights: the account works on the organisation's database `up`, column by column, never on secret columns. A member can only read. An organisation admin can also update and delete content, but cannot insert rows or create tables.
  - Bucket rights: a member can read. An organisation admin can read and write.
  - Renew them with `up-org-credentials`, then open a new terminal (or run `. ~/.config/up/env`). If it fails, your Coder sign-in is too old: restart the workspace.
  - Never copy them into the repository.

## Settings that make it work

- `frontend/.env` keeps `VITE_BACKEND_URL=/api/v1`. `frontend/src/config/env.ts` turns the path into an absolute URL on the page's origin. Vite forwards `/api/` to the backend on `127.0.0.1:21514`.
- Vite answers only to hosts it knows. Coder sets `VSCODE_PROXY_URI` in the workspace. `frontend/vite.config.ts` reads it and allows exactly the host of port 21515.
- Another host needs the shell variable `DEV_ALLOWED_HOSTS` (comma separated; `.example.com` allows every subdomain). Set it on the command line: `DEV_ALLOWED_HOSTS=.example.com npm run dev`. Vite does not read it from `frontend/.env`.
- Without an apps domain on your organisation's Coder, there is no port URL. Run `coder port-forward <workspace> --tcp 21515:21515` on your laptop, then open `http://localhost:21515`.

## Limits (2026-11-18)

- **The port URL is private.** It opens only for you, after the Coder sign-in. Nobody else can open it: no teammate, and not the Up app.
- **Why it cannot be shared:** the platform blocks port sharing. Coder Community cannot limit a shared port to the organisation, so a shared port would be public.
- **The mini-app runs in the SDK simulator** in your browser. The Up app on a phone does not load it.
- **Authenticated routes** (`/me`, `/admin/hello`) answer `503` until the app is registered. They need two things the platform does not hand out yet:
  - The app registered on the organisation's DEV backend. An organisation admin registers it and gives you `HUB_APP_UUID` and `HUB_CLIENT_SECRET` for `backend/.env`.
  - The DEV backend's public key, at `/etc/up-platform/jwt/public.pem` (the default `hub.public_key_path`; the workspace lets you write there). That folder is outside `/home/coder`, so it is emptied at each restart. Keep a copy at `~/hub-public.pem` and copy it back after a restart: `cp ~/hub-public.pem /etc/up-platform/jwt/public.pem`.
  - Once `HUB_APP_UUID` is set, the backend refuses to start without the key file (`Hub public key not found`).
- **The data credentials do not connect yet (2026-11-18).** `~/.config/up/env` names the PROD PostgreSQL host (`postgresql.prod-<slug>`). `up-org-credentials` asks the PROD bucket (`bucket-svc.prod-<slug>`) for keys. The workspace reaches only the DEV hosts. This is on the platform side, outside this repository.
  - PostgreSQL: point your shell at the DEV host. The Vault account is a DEV account.
    ```bash
    export PGHOST="postgresql.dev-${UP_ORG_SLUG}.svc.cluster.local"
    export DATABASE_URL="${DATABASE_URL/prod-${UP_ORG_SLUG}/dev-${UP_ORG_SLUG}}"
    ```
  - Run the two `export` lines again in each new terminal and after each renew: loading `~/.config/up/env` sets the PROD hosts back.
  - Bucket: no temporary keys are written.
- **The demo backend does not use PostgreSQL or the bucket yet.** The credentials are in your environment. Read them in `backend/app/core/config.py` when your backend needs them.
