# api: the mini-app API

A FastAPI (Python 3.14) backend. The mini-app (`../miniapp`) and the Studio plugin (`../plugin`) call it. It runs in your Coder workspace in development and as a Docker image in production.

The architecture and the coding rules are in [`AGENT.md`](AGENT.md). This file is the beginner guide.

## Prerequisites

- In a Coder workspace: nothing to install. `up-project-setup` already ran `uv sync` and wrote `api/.env`.
- On a laptop: [uv](https://docs.astral.sh/uv/) (it installs Python 3.14 for you). You also need your own `api/.env` (see "Environment").

## Install

```bash
cd api
uv sync
```

This creates `api/.venv` from `uv.lock`.

## Run in development

The API runs as production when nothing says otherwise: no `/docs`, no demo routes. Development needs `api/.env` with `ENVIRONMENT=development`. The Coder workspace writes that file. On your own machine run `cp .env.template .env` in `api/` first.

Pick one way.

```bash
cd api
uv run python -m app
```

Or activate the virtual environment first:

```bash
cd api
source .venv/bin/activate
python -m app
```

Check it:

```bash
curl localhost:21514/api/v1/hello
```

Docs of the API: `http://localhost:21514/docs`.

Two commands that do NOT work:

- `python3 -m app` outside the virtual environment fails with `ModuleNotFoundError: No module named 'uvicorn'`. The packages live in `.venv`. Use `uv run python -m app` or activate `.venv` first.
- `uv run ./app` fails with `No module named 'app'`. `app` is a Python package, not a script. Use `python -m app`.

## Environment

`api/.env` is written by the Coder workspace at each start. Git ignores it. Never commit it. The entry point (`python -m app`) loads it, from any folder.

It holds 8 variables: `DATABASE_URL`, `CACHE_URL`, `CACHE_KEY_PREFIX`, `STORAGE_ENDPOINT`, `STORAGE_ACCESS_KEY`, `STORAGE_SECRET_KEY`, `STORAGE_BUCKET`, `HUB_PUBLIC_KEY_PATH`. The table is in the root [`README.md`](../README.md).

A variable that is already set in your shell wins over `api/.env`. The API logs a warning with the name (never the value) when the shell value differs from the file. To see what the API got:

```bash
env | grep -E '^(DATABASE_URL|PGUSER)=' | cut -d= -f1
```

Defaults for everything else: `configs/config.toml`.

## Ports

| Port | What |
| --- | --- |
| 21514 | this API |
| 21515 | the mini-app (`../miniapp`) |
| 21516 | the plugin dev page (`../plugin`) |

In Coder, open the API with the button **API**, the mini-app with **Mini-app** and the plugin with **Plugin**. Coder hides the ports of apps that have a button from "Open ports". The **Plugin** button works only while `plugin/` runs (`npm run dev`).

The API listens on `0.0.0.0`. On a shared network, set `SERVER_HOST=127.0.0.1` to keep it on your machine.

## Tests and lint

```bash
cd api
uv run ruff format . && uv run ruff check .
uv run mypy app tests
uv run pytest
```

## Production image

`api/Dockerfile` builds the image the platform deploys. It has two stages:

1. Build stage (`python:3.14-slim`, pinned by tag and digest): copies `uv`, runs `uv sync --frozen --no-dev --no-install-project` (only the packages of `uv.lock`, in `/app/.venv`), then copies `app/` and `configs/`.
2. Final stage (the same pinned base): copies the whole `/app` of the build stage (`.venv`, `app/`, `configs/`), puts `/app/.venv/bin` first in `PATH`, and runs as the user `10001`, not root. `/app` is read-only for that user.

It sets `ENVIRONMENT=production`, `SERVER_HOST=0.0.0.0` and `SERVER_PORT=<API_PORT>` (build argument, default 8000), then starts `python -m app`. `api.port` in `../miniapp.yaml` is the `API_PORT` the CI passes.

Build and run it on your machine (needs Docker):

```bash
cd api
docker build --build-arg API_PORT=8000 -t miniapp-api .
docker run --rm -p 8000:8000 \
  -e ENVIRONMENT=development \
  -e DATABASE_URL="postgres://user:password@host:5432/db" \
  miniapp-api
curl localhost:8000/healthz
```

`ENVIRONMENT=development` is only for this local test: it also turns on auto-reload inside the container. With `ENVIRONMENT=production` the API refuses to start on the default Hub identity: the platform sets `HUB_APP_UUID` and `HUB_CLIENT_SECRET` itself. The platform also sets `DATABASE_URL`, `CACHE_URL` and the other variables of `../miniapp.yaml` `services`, and mounts the Hub public key at `/etc/up-platform/jwt/public.pem`.

## Deploy from Studio

1. Commit and push to the default branch.
2. In the platform (Studio), open your mini-app and press **Déployer le backend**.
3. The platform builds `api/Dockerfile` in Gitea CI and deploys the new version.

Details: [`../docs/deploy.md`](../docs/deploy.md).

## Common errors

| Error | Cause | Fix |
| --- | --- | --- |
| `ModuleNotFoundError: No module named 'uvicorn'` or `'fastapi'` | You ran `python3 -m app` outside the virtual environment | `uv run python -m app`, or `source .venv/bin/activate` first |
| `ModuleNotFoundError: No module named 'app'` | You ran `uv run ./app` | `uv run python -m app` from `api/` |
| `permission denied for schema public` when creating `demo_visits` | The API connects with the wrong database account. In a Coder workspace, the shell exports a read-only `DATABASE_URL` (`~/.config/up/env`) that wins over `api/.env` | `unset DATABASE_URL PGUSER PGPASSWORD`, then start the API again. The log says `DATABASE_URL is already set in the environment and differs from .env` |
| `503 Authentication is not configured` | The Hub public key is not found (`HUB_PUBLIC_KEY_PATH` missing or wrong) | Check that `api/.env` has `HUB_PUBLIC_KEY_PATH` and that the file exists. Run `up-project-setup` again |
| `connection refused` or timeout on the database | Not in the Coder workspace, or the DEV resources are not ready | Run `up-project-setup`. The demo retries 5 times at start |
