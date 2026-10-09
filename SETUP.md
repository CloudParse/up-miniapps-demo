# SETUP

Prerequisites: Docker, [uv](https://docs.astral.sh/uv/), Node.js >= 25.6.1, `curl`, `jq`, `openssl`, `lsof`.

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

## 4. Claude Code plugin (once)

The SDK ships a Claude Code plugin: the `up-miniapp-builder` skill (exact SDK signatures, tested recipes, mandatory mini-app rules) and the `/new-miniapp` command. Install it from the copy `npm install` just downloaded, in a third terminal at the root of this project:

```bash
claude plugin marketplace add ./up-miniapps-react-template/node_modules/@cloudparse/up-miniapps-sdk/claude-plugin
claude plugin install up-miniapps-sdk@up-miniapps
```

Claude Code keeps its own copy of the plugin. After upgrading the SDK (`npm update` or a new version in `package.json`), reinstall it so the skill matches the new SDK:

```bash
claude plugin uninstall up-miniapps-sdk@up-miniapps
claude plugin install up-miniapps-sdk@up-miniapps
```

## 5. Start Claude Code

From the root of this project (the folder containing `SETUP.md`), so it loads `CLAUDE.md` and `AGENT.md`:

```bash
claude
```

## Stop

```bash
docker compose down
```

## Full reset (if something is broken)

Removes the containers and their volumes (PostgreSQL, Redis, RustFS), stops the backend and the mini-app from steps 2 and 3 if they still run, and deletes the local credentials. Then start again from step 1.

```bash
scripts/reset.sh
```

`scripts/reset.sh --all` also deletes `keys/`, the installed dependencies (`.venv`, `node_modules`), the caches, the mini-app `dist/` and `.env`, for a state as fresh as a new clone. The root `.env` (your port overrides) is kept.
