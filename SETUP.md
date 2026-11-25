# SETUP

How to run your mini-app project in its Coder workspace. How it works and its limits: `docs/coder.md`.

## What the platform did for you

When an admin of your organisation created the mini-app and added you to it:

- the organisation's Gitea got your project's repository, a copy of this demo, named `<organisation>-<mini-app>-<4 characters>`;
- after your first sign-in to your organisation's Coder (`https://coder.<organisation>.<domain>`), you got a workspace named after the mini-app.

At every start, that workspace:

1. clones the repository into `~/<repository>`, once;
2. writes `api/.env` (never commit it) with your mini-app's own DEV database, cache and bucket (`DATABASE_URL`, `CACHE_URL`, `CACHE_KEY_PREFIX`, `STORAGE_ENDPOINT`, `STORAGE_ACCESS_KEY`, `STORAGE_SECRET_KEY`, `STORAGE_BUCKET`: the names production gives too, table in `README.md`), and the DEV backend's public key (`HUB_PUBLIC_KEY_PATH`);
3. installs the dependencies of `api/` (`uv sync`, Python 3.14) and of `miniapp/` (`npm ci`; run `npm ci` in `plugin/` too if you work on the plugin);
4. installs the SDK's Claude Code plugin.

The repository also got `miniapp.yaml` at its root (see "Settings of the mini-app" below).

Nothing to configure. If a step failed (a warning in the workspace's startup log), run it again from a terminal: `up-project-setup`.

## Start the project from the console (Coder workspace)

In the workspace page of Coder, press **Console du projet** (or type `up-dev` in a terminal). One page starts, stops and restarts the API, the mini-app and the plugin, shows their logs and previews, and reloads them when you save a file. Details: `docs/coder.md`, section "The project console". The workspace has 2 CPU cores and 4 GiB of memory: start only what you need.

## Start everything in one command

From the root of the project:

```bash
dev-tools/up-dev.sh start
```

`up-dev.sh` does this:
- starts the API (21514), the mini-app (21515) and the plugin (21516) in the background;
- installs the missing dependencies;
- waits until each part answers;
- prints the address to open for each part.

Other commands:
- `dev-tools/up-dev.sh status` shows what runs. `dev-tools/up-dev.sh logs api` shows the log of a part. `dev-tools/up-dev.sh stop` stops everything.
- Logs are in `.up-dev/` (git-ignored).

Or ask Claude Code: "start everything" ("démarre tout"). The project skill `up-miniapp-start` makes it run this script at once and give you the addresses.

Sections 1 to 3 below start each part by hand, in its own terminal. Use them to see the logs live.

## 1. API (terminal 1)

```bash
cd ~/<repository>/api
uv run python -m app
```

`python -m app` reads `api/.env` itself, with or without `uv run` and from any directory. That file has `ENVIRONMENT=development`: without it the API runs as production (no `/docs`, no demo routes). A variable already set in your shell wins over the file. The API listens on `0.0.0.0:21514`, so the Coder button **API** reaches it (Coder hides the ports of the buttons Mini-app, API and Plugin from "Open ports"; `SERVER_HOST=127.0.0.1` keeps it local). On a laptop (shared Wi-Fi, a café), the API on `0.0.0.0` has no Host check: anyone on the network can read `/docs`, `/openapi.json`, `GET /api/v1/demo` and the public routes. Authenticated routes still need a Hub-signed token. Set `SERVER_HOST=127.0.0.1` to keep it local.

`python -m app` gives the same result as `uv run --env-file` only for plain `KEY=VALUE` values (quotes, comments, `export`). Not supported: `$VAR` expansion and multi-line values. A skipped line is logged by its number, never by its value.

Check it: `curl localhost:21514/api/v1/hello`.

## 2. Mini-app (terminal 2)

```bash
cd ~/<repository>/miniapp
npm run dev
```

## 3. Plugin (terminal 3, optional)

Only if you work on the Studio plugin of the mini-app (`docs/plugin.md`):

```bash
cd ~/<repository>/plugin
npm run dev
```

It listens on port 21516. Open it with the button **Plugin** of the Coder dashboard: `https://plugin--<workspace>--<owner>--<organisation>.cloudparse.app`. The button works only while `plugin/` runs.

## 4. See it live

In the Coder dashboard, open the app **Mini-app** of your workspace (port 21515). The SDK simulator asks which test user to sign in as: pick one. Every save reloads the page.

The button opens `https://miniapp--<workspace>--<owner>--<organisation>.cloudparse.app`. It opens only for you, after the Coder sign-in. The port URL `https://21515--main--<workspace>--<owner>--<organisation>.cloudparse.app` does not open the mini-app (checked 2026-11-23). Use the button address only.

## 5. Deploy to production

`miniapp.yaml` is already a deployable `version: 2` file with the `api`, `services` and `miniapp` sections: adjust them, delete the ones you do not use, the `plugin` section builds the demo plugin of `plugin/` (delete it and the folder if you have none). Commit, push, then press **Déployer le backend**, **Déployer le frontend** and/or **Déployer le plugin** in the platform. A part with no section in `miniapp.yaml` has nothing to deploy: keep its workflow, it ends green and builds nothing (`AGENT.md` section 5.1). Details and the CI contract: `docs/deploy.md`.

## 6. Start Claude Code

Claude Code is ready in the workspace:
- The workspace image ships Claude Code.
- `up-project-setup` installs the SDK's Claude Code plugin (`up-miniapps-sdk`, not the Studio plugin of `plugin/`).
- The project rules (`CLAUDE.md`, `AGENT.md`, `.claude/`) come with the repository.

The workspace has already set up Claude Code for you, so it asks no question: the theme is chosen, the project folder is trusted, the update, telemetry and survey prompts are off, and the permissions are ready (reading and editing in the project, `git status/diff/log/add/commit`, `uv sync`, `uv run`, `npm run`, `up-api`, `up-miniapp`, `up-plugin`, `up-dev`, `rg`, `ls` and `cat` run without a question; `git push`, `curl`, `npx`, `WebFetch` and anything outside the project ask; `rm -rf /`, `curl | sh`, `git push --force` and the platform secrets are blocked as guard rails, not as a security boundary).

The one thing you do once is to sign in with your own Anthropic account: run `claude auth login` in a terminal (or `/login` inside Claude Code). The sign-in stays in `~/.claude` of your home volume.

Your own settings in `~/.claude/settings.json` are kept. To stop the workspace from touching them, create the empty file `~/.claude/up-config.off`.

Start it from the root of the project, so it loads `CLAUDE.md` and `AGENT.md`. The workspace setup script (`up-project-setup`) also writes `CLAUDE.local.md` (root, `api/`, `miniapp/`) with the absolute paths of your workspace. Git ignores it.

```bash
cd ~/<repository>
claude
```

Each time you start `claude`, it shows a welcome message (`.claude/hooks/welcome.py`):
- `miniapp/`: the mini-app, shown inside the Up phone app and, when `deviceTypes` allows it, on the Up website;
- `api/`: its backend, with the database, the cache and the bucket;
- `plugin/`: the admin page in the Studio, where admins put data into the database.

It then asks what you want to build for Up. Describe your idea: Claude plans it with you.

After an SDK upgrade (`npm update` or a new version in `miniapp/package.json`), reinstall the plugin:

```bash
claude plugin uninstall up-miniapps-sdk@up-miniapps
claude plugin install up-miniapps-sdk@up-miniapps
```

## Settings of the mini-app (`miniapp.yaml`)

`miniapp.yaml`, at the root of the repository, holds what the backoffice shows of the mini-app: its identity and how it looks.

- The platform writes it with the values of the backoffice whenever it is missing and those values are known: when it creates the repository, and again if the file is deleted. It never overwrites it.
- The platform reads its deployment sections at each deploy (`docs/deploy.md`).
- CI does not apply its display settings to the backoffice yet (2026-11-20). The value set in the Studio (the backoffice) is the one used. Keep both equal.
- `deviceTypes` is left out (a comment instead) while the backoffice holds no known device.
- Fields: `uuid` and `slug` (never change), `name`, `description`, `logo`, `cardStyle`, `darkTheme`, `deviceTypes`. `miniapp.schema.json` describes each one; editors that read the `yaml-language-server` comment check the file as you type.
- `logo` is the path of a `.webp` image of this repository, for example `assets/logo.webp`; `null` keeps the logo set in the backoffice.
- Never put a secret or an environment variable in it.

## Stop

`Ctrl+C` in the terminals. Stopping the workspace in Coder stops everything; `/home/coder` is kept.
