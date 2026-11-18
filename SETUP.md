# SETUP

Commands to run the demo in your organisation's Coder workspace. How it works and its limits: `docs/coder.md`.

Prerequisites: a Coder workspace of your organisation (git, Node.js 26 LTS and Claude Code are installed there).

## 1. Code and uv (once)

```bash
git clone https://github.com/CloudParse/up-miniapps-demo.git ~/up-miniapps-demo
curl -LsSf https://astral.sh/uv/0.13.9/install.sh | sh
exec zsh
```

uv goes to `~/.local/bin` and installs Python 3.13 itself at `uv sync`.

## 2. Backend (terminal 1)

```bash
cd ~/up-miniapps-demo/backend
cp .env.template .env      # then fill HUB_APP_UUID and HUB_CLIENT_SECRET once the app is registered
uv sync
uv run --env-file .env python -m app
```

Check it: `curl localhost:21514/api/v1/hello`.

## 3. Mini-app (terminal 2)

```bash
cd ~/up-miniapps-demo/frontend
npm install
cp .env.template .env
npm run dev
```

## 4. See it live

In the Coder dashboard, open your workspace and pick port `21515` in the list of open ports:

```text
https://21515--main--<workspace>--<your Coder user>--<slug>.<apps domain>
```

Every save reloads the page. Without an apps domain on your organisation's Coder, run on your laptop `coder port-forward <workspace> --tcp 21515:21515` and open `http://localhost:21515`.

## 5. Claude Code plugin (once)

The SDK ships a Claude Code plugin: the `up-miniapp-builder` skill (exact SDK signatures, tested recipes, mandatory mini-app rules) and the `/new-miniapp` command. Install it from the copy `npm install` just downloaded, in a third terminal:

```bash
cd ~/up-miniapps-demo
claude plugin marketplace add ./frontend/node_modules/@cloudparse/up-miniapps-sdk/claude-plugin
claude plugin install up-miniapps-sdk@up-miniapps
```

Claude Code keeps its own copy of the plugin. After upgrading the SDK (`npm update` or a new version in `package.json`), reinstall it:

```bash
claude plugin uninstall up-miniapps-sdk@up-miniapps
claude plugin install up-miniapps-sdk@up-miniapps
```

## 6. Start Claude Code

From the root of the project, so it loads `CLAUDE.md` and `AGENT.md`. Sign in with your own Anthropic account (`/login`).

```bash
cd ~/up-miniapps-demo
claude
```

## Stop

`Ctrl+C` in terminals 1 and 2. Stopping the workspace in Coder stops everything; `/home/coder` is kept.
