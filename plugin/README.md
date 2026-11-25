# plugin: the Studio plugin

The admin page of your mini-app, shown inside Studio (the backoffice). It is one ES module built with `@cloudparse/up-backoffice-sdk`. It calls the API (`../api`) through the admin routes.

How it is published and how it reaches the API: [`../docs/plugin.md`](../docs/plugin.md). The coding rules are in [`AGENTS.md`](AGENTS.md). This file is the beginner guide.

The plugin is light, like the Studio, and uses the Studio fonts (Figtree for text, Bricolage Grotesque for display titles). The backoffice SDK (0.3.0 and later) carries the palette and the font tokens. The Studio provides the font files. The development page loads them itself (development only). `src/styles.css` only imports the SDK stylesheet. Use the tokens (`bg-card`, `text-foreground`, `border-line`, `bg-soft`, ...) and the SDK components. Never write `bg-white/5`, `text-white` or other opacity colors: they are for a dark page.

Studio loads only published bundles. In development you use a small page that runs the same plugin code with hot reload.

## Prerequisites

- In a Coder workspace: nothing to install except `npm ci` (the setup runs it when `plugin/package-lock.json` exists).
- On a laptop: Node.js 22.18 or newer and npm. The API must run (`../api/README.md`).

## Install

```bash
cd plugin
npm ci
```

## Run in development

Start the API first (terminal 1), then:

```bash
cd plugin
npm run dev
```

- Coder: open the button **Plugin** of your workspace. It works only while `npm run dev` runs in `plugin/` (the port 21516 must listen).
- Laptop: open `http://localhost:21516`.

The page signs in as a DEV test user. Pick another with `?user=<local number>`. The user must be a mini-app administrator, or the API answers 403.

If the API is down, a red message at the top of the page says so and how to start it.

## Ports

| Port  | What                                        |
| ----- | ------------------------------------------- |
| 21516 | this dev page                               |
| 21514 | the API (reached through the proxy `/api/`) |
| 21515 | the mini-app                                |

Coder hides the ports of apps that have a button (**Mini-app**, **API**, **Plugin**) from "Open ports". Use the buttons. The dev server accepts the host of the **Plugin** button (`plugin--<workspace>--<owner>--<org>...`) and the port URL.

## Environment

None to write. The dev server reads:

- `VSCODE_PROXY_URI`: set by Coder. The server allows the host of port 21516 from it.
- `DEV_ALLOWED_HOSTS`: more hosts, comma separated.
- `DEV_HUB_ORIGIN`: the Hub, default `http://backend-service:8080` (the DEV backend of your workspace). On a laptop, set it to a reachable Hub.

## Tests and lint

```bash
cd plugin
npm test
npm run lint
npm run typecheck
npm run build
```

`npm run build` writes `dist/plugin.js`, the file the platform publishes.

## Deploy from Studio

1. Keep the `plugin` section in `../miniapp.yaml`.
2. Commit and push to the default branch.
3. In the platform (Studio), open your mini-app and press **Déployer le plugin**.

Details: [`../docs/deploy.md`](../docs/deploy.md).

## Common errors

| Error                                          | Cause                                                                       | Fix                                                                                |
| ---------------------------------------------- | --------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| `Failed to construct 'URL': Invalid URL`       | A relative API base URL (fixed in `dev/devHost.ts`: the bases are absolute) | Update the template. Do not pass a relative base to `ApiService`                   |
| Red message "The mini-app API does not answer" | The API is not running                                                      | `cd api && uv run python -m app`                                                   |
| `The API refuses this account` (403)           | The test user is not a mini-app administrator                               | Open the page with `?user=<local number>` of an admin test user                    |
| `Blocked request. This host is not allowed`    | The page was opened with an unknown host                                    | Open it from the **Plugin** button. Else `DEV_ALLOWED_HOSTS=your.host npm run dev` |
| `503 Authentication is not configured`         | The API has no Hub public key                                               | See [`../api/README.md`](../api/README.md), "Common errors"                        |
| `permission denied for schema public`          | The API uses the wrong database account                                     | See [`../api/README.md`](../api/README.md), "Common errors"                        |
