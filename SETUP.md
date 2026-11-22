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

## 1. API (terminal 1)

```bash
cd ~/<repository>/api
uv run python -m app
```

`python -m app` reads `api/.env` itself, with or without `uv run` and from any directory. A variable already set in your shell wins over the file. The API listens on `0.0.0.0:21514`, so Coder lists the port in "Open ports" (`SERVER_HOST=127.0.0.1` keeps it local).

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

It listens on port 21516: `https://21516--main--<workspace>--<owner>--<organisation>.cloudparse.app`, or "Open ports" in the Coder dashboard.

## 4. See it live

In the Coder dashboard, open the app **Mini-app** of your workspace (port 21515). The SDK simulator asks which test user to sign in as: pick one. Every save reloads the page.

The same page is on the forwarded port 21515: `https://21515--main--<workspace>--<owner>--<organisation>.cloudparse.app`. It opens only for you, after the Coder sign-in.

## 5. Deploy to production

`miniapp.yaml` is already a deployable `version: 2` file with the `api`, `services` and `miniapp` sections: adjust them, delete the ones you do not use, the `plugin` section builds the demo plugin of `plugin/` (delete it and the folder if you have none). Commit, push, then press **Déployer le backend**, **Déployer le frontend** and/or **Déployer le plugin** in the platform. A part with no section in `miniapp.yaml` has nothing to deploy: keep its workflow, it ends green and builds nothing (`AGENT.md` section 5.1). Details and the CI contract: `docs/deploy.md`.

## 6. Start Claude Code

From the root of the project, so it loads `CLAUDE.md` and `AGENT.md`. The workspace setup script (`up-project-setup`) also writes `CLAUDE.local.md` (root, `api/`, `miniapp/`) with the absolute paths of your workspace. Git ignores it. Sign in with your own Anthropic account (`/login`).

```bash
cd ~/<repository>
claude
```

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
