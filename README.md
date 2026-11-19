# Up Mini-App Demo

A complete Up mini-app with its API: a React mini-app that uses every capability of `@cloudparse/up-miniapps-sdk` (`miniapp/`), and a FastAPI API (`api/`). Every mini-app project of an organisation starts as a copy of it. It runs in the project's Coder workspace, against the organisation's DEV backend and the mini-app's own DEV database, cache and bucket.

Run the commands in [`SETUP.md`](SETUP.md) to get started, then read [`AGENT.md`](AGENT.md): it holds the architecture, the quick start, the conventions and the review checklist. Then read `miniapp/AGENT.md` and `api/AGENT.md`.

How it runs in Coder: [`docs/coder.md`](docs/coder.md).

How it goes to production (two buttons in the platform, Gitea CI, everything configured in `miniapp.yaml`): [`docs/deploy.md`](docs/deploy.md).

The settings of the mini-app (name, description, logo, card style, theme, devices) live in `miniapp.yaml` at the root of each project repository, written by the platform whenever it is missing (never overwritten); [`miniapp.schema.json`](miniapp.schema.json) describes the format. See `SETUP.md`, "Settings of the mini-app".
