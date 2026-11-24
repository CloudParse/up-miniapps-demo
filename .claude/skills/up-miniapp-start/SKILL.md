---
name: up-miniapp-start
description: Start, stop, restart or check the development servers of this project (the API, the mini-app and the plugin) with one command. Use it at once when the user asks to start, run, launch or restart the project, the app, the API, the front end or the plugin, or asks whether they run, in any wording ("start everything", "lance le projet", "démarre tout", "relance l'API", "ça tourne ?").
---

# Start the project

One script runs every part in the background: `dev-tools/up-dev.sh`. Run it from the repository root. Do not explore the project first: the script already knows the folders, the ports and the commands.

## Start everything

```bash
dev-tools/up-dev.sh start
```

What `up-dev.sh start` does:
- starts `api/` (port 21514), then `miniapp/` (port 21515), then `plugin/` (port 21516), each in the background;
- installs missing dependencies first (`uv sync`, `npm ci`);
- waits until each part answers;
- prints the address of each part.

Behaviour:
- A part already running is left as it is. Running `start` twice is safe.
- A failed part gives exit code 1. The script shows the last lines of that part's log.
- An unknown part name gives exit code 1.

One part only: `dev-tools/up-dev.sh start api` (or `miniapp`, `plugin`, several at once).

## Other commands

| Command | What it does |
| --- | --- |
| `dev-tools/up-dev.sh status` | Which part runs, on which port, and the addresses |
| `dev-tools/up-dev.sh logs <part> [lines]` | The last lines of a part's log (default 40) |
| `dev-tools/up-dev.sh restart [part...]` | Stop, then start |
| `dev-tools/up-dev.sh stop [part...]` | Stop (default: all) |

Logs and process ids are in `.up-dev/` (git-ignored).

## After the start

Give the user the addresses the script printed, as they are:
- `Mini-app`: open it to see the mini-app. The SDK simulator asks which test user to sign in as.
- `API`: the API.
- `Plugin`: the development page of the Studio plugin.

In a Coder workspace they are the button addresses (`https://miniapp--<workspace>--<owner>--<organisation>.cloudparse.app`). They open only for the workspace owner, after the Coder sign-in. Never give the port URLs (`https://21515--main--...`): they do not open the pages.

## When a part fails

1. Read the log: `dev-tools/up-dev.sh logs <part> 80`.
2. Common causes:
   - `api/.env` is missing: in a Coder workspace, run `up-project-setup`. Never read nor print `api/.env`.
   - `production runs with the DEV mock registration`: `api/.env` is missing or has no `ENVIRONMENT=development`. Run `up-project-setup`.
   - `permission denied for schema public`, or a database, cache or bucket error: the DEV resources. See `docs/coder.md`.
   - A port already answers but the script did not start it: the user started it in a terminal. Ask them to stop it there (`Ctrl+C`), then start again.
3. Fix the cause, then `dev-tools/up-dev.sh restart <part>`.

The servers reload on their own when a file changes. Restart a part only after a change of `api/.env`, of a dependency or of a Vite config.
