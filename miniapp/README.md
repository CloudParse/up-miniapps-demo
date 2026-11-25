# miniapp: the mini-app (React)

The mini-app users open in the Up app. React + Vite + `@cloudparse/up-miniapps-sdk`. It calls the API (`../api`).

The architecture and the coding rules are in [`AGENTS.md`](AGENTS.md). This file is the beginner guide.

## How the mini-app is shown

- The SDK is pinned to `@cloudparse/up-miniapps-sdk` 0.17.0. That version draws the phone mock by itself on the Up web launcher. Do not add an SDK version older than 0.17.0.
- On the Up web launcher on a computer, the mini-app runs inside a phone mock. The person picks the device (Pixel, iPhone, tablet) above the app.
- On the Up web launcher on a phone, there is no mock: the mini-app fills the screen, like in the Up app. The exit button of the mini-app goes back to the list of mini-apps.
- You change nothing for this. `<SDKProvider>` reads `window.__UP_RENDER_AS__`, which the launcher sets. The `edgeToEdge` prop of `<SDKProvider>` only changes the simulator you get in a plain browser (`npm run dev`).
- Build with the pinned SDK (`npm ci`) before you upload the bundle in the Studio. A bundle built with an older SDK shows no phone mock.

## Prerequisites

- In a Coder workspace: nothing to install. `up-project-setup` already ran `npm ci` and copied `.env.template` to `.env`.
- On a laptop: Node.js 22.18 or newer and npm.

## Install

```bash
cd miniapp
npm ci
cp -n .env.template .env
```

## Run in development

Start the API first (terminal 1, see [`../api/README.md`](../api/README.md)), then:

```bash
cd miniapp
npm run dev
```

The dev server listens on port 21515. It forwards `/api/` to the API on 21514 and `/hub/` to the DEV Hub.

- Coder: open the button **Mini-app** of your workspace. The SDK simulator asks which test user to sign in as.
- Laptop: open `http://localhost:21515`.

## Ports

| Port  | What                |
| ----- | ------------------- |
| 21515 | this dev server     |
| 21514 | the API             |
| 21516 | the plugin dev page |

Coder hides the ports of apps that have a button (**Mini-app**, **API**, **Plugin**) from "Open ports". Use the buttons.

## Tests and lint

```bash
cd miniapp
npm test            # the Host guard of the dev server
npm run typecheck
npm run check       # biome: lint + format check
npm run check:write # fix what biome can fix
```

## Build

```bash
npm run build
```

The output is `dist/`, one HTML file. The platform builds it the same way.

## Deploy from Studio

1. Commit and push to the default branch.
2. In the platform (Studio), open your mini-app and press **Déployer le frontend**.

Details: [`../docs/deploy.md`](../docs/deploy.md).

## Common errors

| Error                                                                                                                       | Cause                                                        | Fix                                                                                                           |
| --------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------- |
| `Blocked request. This host is not allowed` (Vite) or `Blocked request: this host is not allowed (DEV_ALLOWED_HOSTS)` (403) | The page was opened with a host the dev server does not know | Open it from the Coder button. Else `DEV_ALLOWED_HOSTS=your.host npm run dev`. Several hosts: comma separated |
| `npm: command not found` or missing `node_modules`                                                                          | Dependencies not installed                                   | `npm ci`                                                                                                      |
| The page loads but calls fail (502 on `/api/...`)                                                                           | The API is not running                                       | Start it: `cd api && uv run python -m app`                                                                    |
| `503 Authentication is not configured` from the API                                                                         | The API has no Hub public key                                | See [`../api/README.md`](../api/README.md), "Common errors"                                                   |
