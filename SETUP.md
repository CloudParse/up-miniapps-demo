# SETUP

How to run your mini-app project in its Coder workspace. How it works and its limits: `docs/coder.md`.

## What the platform did for you

When an admin of your organisation created the mini-app and added you to it:

- the organisation's Gitea got your project's repository, a copy of this demo, named `<organisation>-<mini-app>-<4 characters>`;
- after your first sign-in to your organisation's Coder (`https://coder.<organisation>.<domain>`), you got a workspace named after the mini-app.

At every start, that workspace:

1. clones the repository into `~/<repository>`, once;
2. writes `api/.env` (never commit it) with your mini-app's own DEV database, cache and bucket, and the DEV backend's public key;
3. installs the dependencies of `api/` (`uv sync`, Python 3.14) and of `miniapp/` (`npm ci`);
4. installs the SDK's Claude Code plugin.

Nothing to configure. If a step failed (a warning in the workspace's startup log), run it again from a terminal: `up-project-setup`.

## 1. API (terminal 1)

```bash
cd ~/<repository>/api
uv run --env-file .env python -m app
```

Check it: `curl localhost:21514/api/v1/hello`.

## 2. Mini-app (terminal 2)

```bash
cd ~/<repository>/miniapp
npm run dev
```

## 3. See it live

In the Coder dashboard, open the app **Mini-app** of your workspace (port 21515). The SDK simulator asks which test user to sign in as: pick one. Every save reloads the page.

Without the app (no apps domain on your organisation's Coder), run on your laptop `coder port-forward <workspace> --tcp 21515:21515` and open `http://localhost:21515`.

## 4. Start Claude Code

From the root of the project, so it loads `CLAUDE.md` and `AGENT.md`. Sign in with your own Anthropic account (`/login`).

```bash
cd ~/<repository>
claude
```

After an SDK upgrade (`npm update` or a new version in `miniapp/package.json`), reinstall the plugin:

```bash
claude plugin uninstall up-miniapps-sdk@up-miniapps
claude plugin install up-miniapps-sdk@up-miniapps
```

## Stop

`Ctrl+C` in terminals 1 and 2. Stopping the workspace in Coder stops everything; `/home/coder` is kept.
