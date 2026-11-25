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
- Claude Code is ready. The image ships it, `up-project-setup` installs the SDK's Claude Code plugin, and the project rules come with the repository. The workspace has already set it up (`up-claude-config`, at every start): theme, trust of the project folder, permissions (the daily loop without a question, see "Claude Code in the workspace: what it does without asking" below), no auto-update, no telemetry and no survey. The only thing you do once is to sign in with your own Anthropic account: `claude auth login` (or `/login`). Your own settings are kept: the script only adds; an empty file `~/.claude/up-config.off` stops it. Each time you start `claude`, it shows a welcome message about `miniapp/`, `api/` and `plugin/` and asks what you want to build for Up (`SETUP.md`, section 6).
- No Docker daemon. No root: you are `uid 1000`.
- Over the network: the organisation's coderd, its DEV backend, DEV PostgreSQL, DEV cache and DEV bucket, its Gitea and Vault, plus DNS and the internet. No Kubernetes API.
- Only `/home/coder` survives a restart. Keep the project and every tool you install there.
- Git: the repository's remote is your organisation's Gitea, with your own account (Coder asks you to connect it once).

## Settings that make it work

- `miniapp/.env` keeps `VITE_BACKEND_URL=/api/v1`. Vite forwards `/api/` to the API on `127.0.0.1:21514`, and `/hub/` to the DEV backend (`DEV_HUB_ORIGIN`, default `http://backend-service:8080`).
- Vite answers only to hosts it knows. Coder sets `VSCODE_PROXY_URI` in the workspace: `miniapp/vite.config.ts` allows exactly two hosts (`plugin/vite.dev.config.ts` does the same with the button **Plugin**: `plugin--<workspace>--<owner>--<org>.<apps domain>`): the port URL of 21515 (`21515--<agent>--<workspace>--<owner>--<org>.<apps domain>`) and the link of the dashboard button "Mini-app" (`miniapp--<workspace>--<owner>--<org>.<apps domain>`). Another host needs the shell variable `DEV_ALLOWED_HOSTS` (comma separated; `.example.com` allows every subdomain).

- The Vite dev server (21515), the plugin's development page (21516, `docs/plugin.md`) and the API (21514) listen on `0.0.0.0`. Coder lists only the ports that listen on every interface in "Open ports". The two Vite servers answer 403 to any Host header that is not the Coder port URL, the host of the dashboard button, `DEV_ALLOWED_HOSTS` or a loopback name, IP addresses included (`dev-tools/hostGuard.ts`; Vite 8 alone lets IP Host headers through `allowedHosts`). The API (`api/configs/config.toml`, `server.host`) has no such check. On a laptop (shared Wi-Fi, a café), the API on `0.0.0.0` has no Host check: anyone on the network can read `/docs`, `/openapi.json`, `GET /api/v1/demo` and the public routes. Authenticated routes still need a Hub-signed token. Set `SERVER_HOST=127.0.0.1` to keep it local. A deployed container sets `SERVER_HOST=0.0.0.0` itself (`api/Dockerfile`), so production is unchanged.
- `api/.env` is read by `python -m app` itself (`api/app/core/dotenv.py`), with or without `uv run`. A variable already set in the shell wins over the file. `python -m app` gives the same result as `uv run --env-file` only for plain `KEY=VALUE` values (quotes, comments, `export`). Not supported: `$VAR` expansion and multi-line values. A skipped line is logged by its number, never by its value.

## When the workspace runs

- Your workspace is created AHEAD, when you become a developer and for each mini-app you administer. It is created **stopped**: no pod runs until you press **Start** in Coder.
  - Coder shows it with its **Start** button. Press it when you want to work. It takes a short moment to start.
  - For a few seconds after its creation Coder can show it as "Running" with nothing started. The platform stops it by itself right after the first build, a few seconds, and at the latest within about 20 seconds plus the time of the stop build. The Start button then appears.
  - If you press Start inside that short window, the platform stops the workspace once. Press Start again.
  - Coder shows no warning. Nothing starts before you press Start.
- **Ouvrir mon workspace** in the Studio opens your workspace page in Coder. If the workspace does not exist yet, the click creates it, stopped as well: press **Start** in Coder. The click never starts a pod.
- Every **Ouvrir mon workspace** entry does the same: the button on the page of a mini-app, the link in the sidebar, the link on the home page, the "Coder" line of the services and the card of the components page.
- An entry that is not on a mini-app page uses your mini-apps. With one mini-app it opens that workspace. With several it shows a short list to choose from. With none it says "Aucune mini-app à ouvrir.".
- The first time, the button opens the Coder sign-in page. Sign in with the account you use in the Studio. After the sign-in Coder shows your workspace, which is already there, stopped. Press **Start**.
- If your organisation was deployed before template 0.5.13, nothing is created ahead and the click says "Ton organisation doit être redéployée avec le dernier modèle Coder.": ask a manager to redeploy the organisation.
- If the workspace page shows a failure, press **Start**. A person never gets a second workspace for the same mini-app.
- A workspace that you started and left unused for 5 minutes after its creation is stopped on its own, and one left running without use is stopped after 2 hours.
- A workspace created before 2026-11-23 can show the Coder warning "Ephemeral Parameters Detected" when you press Start. In Coder, open the workspace and press **Update** to get the current template (0.5.13): the warning is gone after it, and the workspace keeps its files.
- The workspace has a parameter "Créé sans pod" (`hold_first_start`) managed by the platform. Do not change it: the platform sets it back to false so that your Start runs the pod.
- Cost of the workspaces created ahead:
  - A workspace created ahead (held) has no pod. Its home volume (10 GiB requested) is created with it, empty and unbound: it uses no disk until your first **Start** mounts it. Every stop keeps it. Only the developers of a mini-app get a workspace of it.
  - The Coder namespaces use the StorageClass `local-path` (`WaitForFirstConsumer`): a started workspace grows without a limit per volume, and a deleted workspace keeps its directory on the node (`Retain`).
  - The namespace of your organisation accepts 60 started workspaces (one volume claim each, 10 GiB nominal each). A workspace of a mini-app you started once keeps its claim until it is deleted. There is no other per-person limit for now.
  - The running workspaces are bounded by the memory of your organisation: each takes 4 GiB while it runs. A **Start** above it fails with "exceeded quota: coder-workspaces": stop a workspace you do not use, or ask a super user to raise the memory of the organisation. The node has a real limit too: when it is full a Start waits ("Workspace agent is connecting") until a workspace stops.
  - A workspace stops by itself after 2 hours without use (the activity of VS Code, a terminal or the apps extends it by 1 hour).
  - The platform creates at most 500 workspaces ahead per organisation. It logs a warning when the cap is reached.
- A workspace stopped for a while keeps `/home/coder`: your files and installed tools are still there when it starts again.

## When the workspace is ready (template 0.5.17)

- Pressing **Start** runs the startup script. The workspace is ready only when the whole script has ended well. Until then every button stays disabled and terminal logins wait. If the script ends in failure the buttons become clickable again, but the editor is not running (alert icon): read the startup log.
- The script first waits for your project. A new mini-app, its Git repository and your access to it are prepared by the platform at the same time, so the repository can be missing for a short while. The script retries with a growing delay for up to 10 minutes and writes what it waits for in the startup log of the workspace page, in French then English.
- Then it clones the repository, checks that it has a commit, writes the DEV settings (`api/.env`) and installs the dependencies. Each of these steps is tried again when it fails.
- If a step still fails, the log ends with "Le workspace n'est PAS prêt" and the editor is not available (its button shows an alert icon "Unhealthy"). The workspace keeps trying in the background for 2 hours: when the repository appears, the **VS Code** alert icon goes away by itself. You can also stop and start the workspace again: every step is repeated and a half-done step is finished, nothing is lost.
- A message "dépôt introuvable ou accès pas encore accordé" means the repository does not exist yet or your access to it is not granted yet. Wait a minute, then start the workspace again.

## The banner "Workspace agent is connecting"

- Coder shows it from the moment the pod exists until the workspace agent has connected. It is Coder's own message: nothing in the template can hide it.
- The agent should connect within a few seconds after the pod starts (template 0.5.17; 30 seconds more before). The first start after a new template release also downloads the workspace image once (about 30 seconds); later starts do not.
- Then the startup log runs (about 40 seconds: repository, settings, dependencies, editor). The workspace is ready when the log ends with "Workspace prêt / workspace ready".
- If the banner stays for more than 3 minutes, open the startup log on the workspace page and restart the workspace.

## The project console

One page starts, stops and restarts the three parts of the project. In the workspace page of Coder, press **Console du projet** (it opens a tab). The console runs from the end of the startup, so the button is ready with the workspace. If it is not (a restart of the console, an older workspace), type `up-dev` in a terminal: it starts the console and prints its address. `up-dev stop` stops it with the three parts, `up-dev status` tells whether it runs.

What the page shows:
- One card per part, with a short explanation (what it is, its port, its folder, the exact command it runs), its state (arrêtée, démarrage, en marche, plantée) and three buttons: **Lancer**, **Redémarrer**, **Arrêter**.
- A link per part, opening it alone in a new tab: **Tester l'API** (the API documentation), **Voir la mini-app**, **Voir le plugin**.
- The mini-app and the plugin side by side, in two previews. Each part updates itself when you save a file: Vite pushes the change to the page through its own WebSocket (hot reload), and the API reloads its code (uvicorn). If a preview stays empty, open the part alone with its link.
- The live log of each part (the last 500 lines, streamed by WebSocket), in a drawer over the bottom of the page. The page reconnects by itself.
- The memory of the workspace (see "Memory and CPU").

Room for the previews:
- The header is one slim line. **Masquer les services** hides the three cards. The state of each part stays in the header, with the buttons ▶ (lancer), ↻ (redémarrer) and ■ (arrêter), so you keep control without opening the cards. **Afficher les services** brings them back. An error of an action stays visible in the header.
- With the cards hidden, the two previews fill the window under the header (more than 90 % of its height). The phone of the mini-app shrinks to fit the height. With the cards shown, the previews keep at least 60 % of the window height and the page scrolls.
- **Journaux ▸** opens the logs as a drawer (40 % of the window height) over the previews, with a tab per part and **Effacer l'affichage**. It never takes height from the previews.
- **Aperçus plein écran** hides the cards and the logs in one click. **Échap** leaves the full screen. Pressed again, it closes the logs. The log drawer covers the bottom 40 % of the window while it is open.
- Keys (when the page has the focus, not an iframe): **P** full-screen previews, **L** logs, **S** services, **Échap** leave full screen or close the logs. The choice of cards and logs is kept in this browser (`localStorage`, key `console.layout`); the full-screen mode is never kept. By default the cards are shown and the logs closed.

What it runs, exactly (nothing else, no command typed in the page):

| Part | Port | Folder | Command |
| --- | --- | --- | --- |
| API | 21514 | `api/` | `SERVER_HOST=0.0.0.0 uv run --env-file .env python -m app` |
| Mini-app | 21515 | `miniapp/` | `node_modules/.bin/vite --host 0.0.0.0` (what `npm run dev` runs, without the npm process) |
| Plugin | 21516 | `plugin/` | `node_modules/.bin/vite --config vite.dev.config.ts` |

Rules of the console:
- A part started in a terminal (`up-api`, `dev-tools/up-dev.sh`) shows "lancée ailleurs": the console does not stop what it did not start. Stop it where it runs.
- A part that cannot start says why (`api/.env` or `node_modules` missing: run `up-project-setup`; port already in use; not enough memory).
- A part that exits by itself shows "plantée" with its exit code. Read its log. A restart clears it.
- Stopping the console stops the parts it started. Restarting the workspace stops everything.
- A secret never appears in the page: the values of `api/.env` that look like secrets, tokens and the password of a connection URL are replaced by `***` in the logs.

Safety of the console:
- It listens on `127.0.0.1` only. In Coder it is reached by the app **Console du projet**, owner only, behind the Coder sign-in.
- It checks the `Host` header of every request and WebSocket with the same list as the two Vite servers (`dev-tools/hostGuard.ts`): the Coder button address, `DEV_ALLOWED_HOSTS`, loopback names, never an IP address.
- An action (`POST`) needs the `Origin` of the console and a random token that only the console page holds. At most one action per part every 2 seconds, 30 per minute.
- It serves no file and takes no path, command or argument from a request.
- Code: `dev-tools/console/` (`server.ts`, `supervisor.ts`, `security.ts`, `mask.ts`, `ws.ts`, `memory.ts`, `page.html`), no dependency. Tests: `npm test` in `miniapp/`.
- Agents (Claude Code) keep using `dev-tools/up-dev.sh` (no browser needed). The console and the script do not share state: use one or the other for a given part.

## Memory and CPU

Every workspace is capped at **2 CPU cores and 4 GiB of memory** in total. The cap is in the template, not in a setting: nobody can raise it from the workspace. The card shows "CPU 0.1/2" and "Mémoire 0.3/4.0 GiB" against that limit.

Measured on a workspace of this template (image 0.5.17, 2026-11-25):
- the three parts running (API with its reload worker, mini-app, plugin) and the console: about 930 MiB of process memory;
- Vite alone: about 330 MiB at rest, up to 500 MiB after the page loaded. Each Vite server runs with a cap on its JavaScript heap (384 MiB for the mini-app, 320 MiB for the plugin): a runaway server stops with "JavaScript heap out of memory" instead of filling the workspace;
- VS Code in the browser (code-server) takes 0.3 GiB idle and up to 1.2 GiB with a window open; Claude Code takes about 0.6 GiB; the Coder agent about 0.2 GiB.

So 4 GiB holds the editor, Claude Code and the three parts together with room to spare, but not unlimited growth. Advice:
- Start only the parts you need. The console shows the memory in its header and refuses to start a part when less than 200 MiB is free.
- Close the VS Code windows and terminals you do not use.
- When the memory is full the sandbox kills a process. The console starts the parts with a higher kill priority than the workspace agent, so a dev server goes first; start it again from the console.

## Are the Mini-app, API and Plugin buttons ready?

- The buttons **Mini-app** (port 21515), **API** (21514) and **Plugin** (21516) show an alert icon and the text "Unhealthy" while nothing listens on their port. Coder 2.39 still lets you click them: the page then fails to load. A server that answers a status 500 or more on `/` is also "Unhealthy", while the card says "en marche". Start the part first, from the console.
- The workspace page lists one fact per item, each a label and a short value, refreshed every 5 seconds (the value is never cut):
  - **Projet**: "prêt", or "préparation" while the startup runs (see the startup log).
  - **Console**: "ouverte", or "tape up-dev".
  - **API**, **Mini-app**, **Plugin**: "en marche" or "arrêtée". The plugin says "pas de plugin/" when the project has no `plugin/` folder.
  - **CPU**, **Mémoire**: use against the cap above. **Disque**: what you have used in your home, against its nominal 10 GiB ("1.2/10 Go", counted every 5 minutes, "calcul..." the first time). The card no longer shows the disk of the machine.
- From a terminal, three short commands do the same as the console, one part each, from any folder. Each runs in the foreground, so its logs stay on screen, and Ctrl+C stops it. Each refuses with a clear message when the project is not ready, `api/.env` or `node_modules` is missing or its port is already in use. `up-status` says which of the three runs.
  - `up-api` runs `cd api && SERVER_HOST=0.0.0.0 uv run --env-file .env python -m app`
  - `up-miniapp` runs `cd miniapp && npm run dev -- --host 0.0.0.0`
  - `up-plugin` runs `cd plugin && npm run dev`
- The check reaches `127.0.0.1` inside the workspace. A server that listens on `127.0.0.1` or on `0.0.0.0` is "en marche". A server that listens only on `::1` (Node's `localhost` can resolve to `::1`) is not: use `--host 0.0.0.0`.

## Claude Code in the workspace: what it does without asking (2026-11-25)

The workspace writes `~/.claude/settings.json` and `~/.claude.json` at every start (`up-claude-config`). The one thing you do once is `claude auth login`. These lists are guard rails, not a security boundary: a shell pattern can be evaded, and the pod is the sandbox. The pod holds your own DEV credentials (`api/.env`, `~/.config/up`, your sign-in token), so the lists protect those first.

| Claude peut faire sans demander | Why |
|---|---|
| `git status`, `diff`, `log`, `show`, `blame`, `rev-parse`, `remote -v`, `config --get` | Read only. |
| `git add`, `commit`, `push` (only `git push`, `git push origin ...`, `git push -u origin ...`; never forced), `pull` (bare, from `origin`, `--rebase`) and `fetch` (bare, from `origin`, `--all`, `--prune`), `checkout`, `switch`, `branch`, `merge`, `rebase`, `stash`, `reset` (soft and mixed), `tag`, `restore --staged` | The daily loop. A push goes to the project's own Gitea, whose branch protection applies. |
| `npm install` and `npm i` with no package name, `npm ci`, `npm run`, `npm test`, `npm ls`, `npm outdated`, `npx --no-install` | They install what `package.json` and the lock file already say. `--no-install` stops `npx` from downloading a package. |
| `node`, `tsc`, `biome`, `vitest`, `python`, `python3`, `pytest`, `ruff`, `mypy`, `make` | They run the project's own code: that is development. They also run any code Claude just wrote, and no string rule can stop an interpreter. Accepted. |
| `uv sync`, `uv lock`, `uv run`, `uv tree`, `uv pip list`, `uv pip show` | Same as npm: what `pyproject.toml` and `uv.lock` already say. |
| `ls`, `cat`, `head`, `tail`, `wc`, `pwd`, `rg`, `grep`, `jq`, `diff`, `tree`, `which`, `ps` (plain, `aux`, `-ef`), `date`, `du`, `df`, `free`; Read, Glob, Grep | Read only or harmless. The secret paths below are refused first. |
| `mkdir`, `cp`, `mv`, `touch`, `sed`; Edit and Write | Claude Code's own `acceptEdits` mode, inside the project (and `~/<repo>`) only. A path outside still asks. |
| `up-curl http://localhost:21513-21516/...` (the dev servers) | A GET of the API, Vite or the console, and nothing else: one address, no other option. Plain `curl` asks. |
| `up-api`, `up-miniapp`, `up-plugin`, `up-dev`, `up-status` | The workspace's own start commands. |

| Demande | Why |
|---|---|
| `git reset --hard`, `--merge` or `--keep`, `git clean`, `git checkout -f`, `git checkout -- <path>`, `git checkout <ref> .`, `git switch -f`, `git restore <path>` or `--worktree`, `git stash drop` or `clear`, `rm`, `rmdir` | They throw work away. |
| `git branch -D`, `-d`, `-m`, `-f`, `git tag -d`, `-f`, `git push --delete` or `-d`, `git rebase -i` | They delete or rewrite history. The project hook blocks most of them anyway (it also blocks a delete by `git push origin :branch`). |
| `npm install <package>`, `npm update`, `npx` without `--no-install`, `uv add`, `uv lock` or `uv sync` with `--upgrade`, `-U`, `-P`, `uv run --with` | A new or changed dependency is where a supply-chain attack enters: its install scripts run with your DEV credentials in reach. It asks when a command names the package. Editing `package.json` or `pyproject.toml` and then running `npm install` or `uv sync` does not ask. |
| `WebFetch`, `WebSearch`, `curl`, `wget`, `ssh`, `scp`, `nc` | They send what Claude knows to the network, or fetch text that can carry a prompt injection. |
| `kill`, `pkill`, `docker`, `psql`, `git clone`, any command not listed | Not in the loop above. Anything outside the project folder asks too. |

| Interdit | Why |
|---|---|
| `git push --force`, `-f`, `-uf`, `--force-with-lease`, `+branch`, `:+branch`, `--mirror`; `git push` to a URL or with `@`; `git --receive-pack`, `--upload-pack`, `--exec`, `--output` | Rewrites the shared history, or sends the code or runs a command elsewhere. |
| `rm -rf` of `/`, `~`, `$HOME`; `curl` or `wget` piped to `sh` or `bash` | Destroys the workspace, or runs unknown code. |
| `env`, `printenv`, `set`, `export -p`, `declare -p`; any command or Read naming `~/.config/up`, `api/.env`, `~/.claude/.credentials.json`, `.git-credentials`, `.ssh/`, `/proc/*/environ`; `cat`, `head`, `tail`, `grep`, `rg` of a `.env` file | They print secrets (database and cache passwords, your sign-in token, your Anthropic login, your keys). |
| Any command naming `.claude/settings`, `.claude.json`, `.bashrc`, `.zshrc`, `.profile`; Edit of those files | A prompt injection could widen its own permissions or persist. Read of the project's own `.claude/settings.json` still works through the Read tool. |

The project's own `.claude/settings.json` and its hook (`.claude/hooks/guard.py`) add their own blocks (protected files, force pushes, branch and tag deletion, history rewrites, deleting outside the project). Rules from three places add up and a deny always wins. Your own entries in `~/.claude/settings.json` are kept; the script only adds. An existing project created before 2026-11-25 still has `git push` and `curl` in its own ask list (`.claude/settings.json`): they ask there until a maintainer removes those two lines. Claude Code does not enable `bypassPermissions` or auto mode here. Your home folder is not marked as trusted (trust is inherited by every repository below it): start `claude` in the project, as the terminals do.

## Your shell and the project settings

- The terminal of the workspace already has the project variables (`DATABASE_URL`, `CACHE_URL`, `STORAGE_*` and the others of the table above), the same names as in `api/.env`. `psql "$DATABASE_URL"` works in a new terminal.
- The workspace writes `AGENTS.local.md` (and one per folder, plus `CLAUDE.local.md` = `@AGENTS.local.md`) at each start: the absolute paths, the commands and the ports of this workspace. Every agent reads them. Git ignores them.
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

## Where to open the mini-app (2026-11-23)

- The app "Mini-app": `https://miniapp--<workspace>--<owner>--<organisation>.cloudparse.app`. The address has no agent name.
- The port URL `https://21515--main--<workspace>--<owner>--<organisation>.cloudparse.app` does not open the mini-app (checked 2026-11-23). Use the button address only.
- The app "API" (port 21514) and the app "Plugin" (port 21516, the development page of `plugin/`): same URL shape with `api--` and `plugin--`. The three buttons (Mini-app, API, Plugin) hide their ports from "Open ports". The Plugin button needs the plugin running: `up-plugin` (`npm run dev` in `plugin/`), or `dev-tools/up-dev.sh start` from the root (it starts the three parts).
- `cloudparse.app` is the apps domain of the production platform, shared by every organisation's Coder.
- The buttons open only for you, after the Coder sign-in. The apps are owner-only.

## Limits (2026-11-20)

- **The app URL is private.** It opens only for you, after the Coder sign-in. The platform blocks port sharing: Coder Community cannot limit a shared port to the organisation.
- **The mini-app runs in the SDK simulator** in your browser. The Up app on a phone does not load it. To see it as a member does on the website, publish a bundle and open the web launcher: [web-launcher.md](web-launcher.md).
- **The workspace is not production.** Production is deployed from the Studio: [deploy.md](deploy.md).
