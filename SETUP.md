# SETUP

Prerequisites: Docker, [uv](https://docs.astral.sh/uv/), Node.js >= 25.6.1, `curl`, `jq`, `openssl`.

## 1. Environment (once)

```bash
scripts/generate-keys.sh
docker compose up -d --wait
scripts/register-miniapp.sh
```

## 2. Backend (terminal 1)

```bash
cd up-miniapps-template-python-backend
uv sync
uv run --env-file .env python -m app
```

API docs: http://localhost:21514/docs

## 3. Mini-app (terminal 2)

```bash
cd up-miniapps-react-template
npm install
cp .env.template .env
npm run dev
```

Open http://localhost:21515

## Stop

```bash
docker compose down        # keep data
docker compose down -v     # wipe data (then re-run step 1's register script with FORCE=1)
```
