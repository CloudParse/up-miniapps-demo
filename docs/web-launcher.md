# The web launcher: your mini-app on the Up website

People open a mini-app in the Up app on a phone, and also on the Up website (the "web launcher"). This page explains what the website does with your mini-app and what you must know when you build it. Last audited: 2026-11-23.

## Which mini-apps show on the website

- Only mini-apps with the web platform enabled and a published bundle. Publish a bundle with the button **Déployer le frontend** in the Studio (`docs/deploy.md`).
- The website shows the app to the members of the organisation. Test it as a member (a person without Studio rights), not only as an admin.

## How it looks

| Where the person is | What they see |
| --- | --- |
| A computer | Your mini-app inside a phone mock. A control **Écran** above the app picks the device: Pixel 10, iPhone 16, Galaxy Tab S9, iPad Air. The choice is kept in the browser and restarts the app. |
| A phone, or a narrow window | No mock. The mini-app fills the whole page, like in the Up app. The exit button of the mini-app (`sdk.ui.exit()`) goes back to the list of mini-apps. |
| A phone, in Chrome or Brave on Android | A small **Plein écran** button hides the address bar and the browser buttons. It needs a tap. |
| A phone, in Safari on iPhone | Safari has no fullscreen API for a page. Use **Add to Home Screen** in the share menu: the site then opens without any browser bar. |
| A phone, site added to the home screen | Already without browser bars. The **Plein écran** button is not shown. |

You write nothing for this. `<SDKProvider>` of `@cloudparse/up-miniapps-sdk` 0.17.0 reads `window.__UP_RENDER_AS__`, which the launcher sets, and draws the phone mock by itself. Rules:

- Pin the SDK to 0.17.0 or newer (`miniapp/package.json` does). An older SDK draws no mock.
- Build with `npm ci` before you upload the bundle. The bundle contains the SDK version of your lock file.
- Use `h-full` or `100%` for the height of your layout, not `100vh`. In the phone mock the screen is a box smaller than the browser window. `miniapp/src/components/layout/AppShell.tsx` shows how.
- The `edgeToEdge` prop of `<SDKProvider>` only changes the simulator you get in a plain browser (`npm run dev`).

## How your code runs in the frame

The website runs your bundle in a sandboxed frame (`sandbox="allow-scripts allow-forms"`, no `allow-same-origin`). Consequences:

- Your code cannot read the website's cookies, storage or DOM. This is by design.
- `localStorage` and `sessionStorage` exist but live in memory for the life of the tab. Use `sdk.storage` for anything you want to read again.
- A Web Worker made from a `Blob` works (the map libraries do this). The `fetch` of a `blob:` URL of your own Blob works too.
- Your network calls go through the host bridge (`sdk.network`, `createApiService`). They carry the person's token for your mini-app, only toward your backend and the origins in `allowedOrigins`.

## What the web host supports

The website answers the bridge requests below. Everything else answers `<REQUEST> is not supported by the UP web host`.

| Works | Does nothing (accepted, no effect) | Not supported on the website |
| --- | --- | --- |
| `sdk.initialize`, context, user profile, network requests, storage and secure storage (in memory), permissions request, exit | debug log, scroll configuration, system bars, haptics | fidelity points (balance, history, spend), location, camera and QR scan, media, payment, achievements, routing and navigation, activity |

Design your screens so that an unsupported capability shows a clear message, not a crash. `miniapp/src/lib/errors.ts` turns the web host answer into a French message for the person, and every card of the demo uses it.

## Where the backend addresses come from

A mini-app never carries the address of its backend. The platform gives it, in this order of precedence (the SDK does the work in `createApiService` and `createWsService`):

1. `window.__UP_BACKEND_URLS__` (`{ http, ws }`): set by the launcher before your code runs, from the addresses registered for the mini-app.
2. `sdk.getEnv()` (`backendUrl`, `wsBackendUrl`): filled by `sdk.initialize()`.
3. An `UPDATE_CONTEXT` event with a new `env`: sent when the backend is deployed after the person opened the app. The launcher asks the platform again every 8 seconds for 10 minutes while the address is missing.
4. Your own default (`VITE_BACKEND_URL` in development only).

Registered addresses follow one convention: `https://api.<mini-app>.app.<domain>/api/v1` for HTTP and `wss://api.<mini-app>.app.<domain>/api/v1/ws` for the WebSocket. Never put them in the code.

## Test it

1. Publish the bundle (button **Déployer le frontend**) and deploy the backend (button **Déployer le backend**).
2. Open the website as a member: `https://<organisation domain>/o/<organisation>/apps`.
3. On a computer, try each device of the **Écran** control. On a phone, check the fullscreen display and the exit button.
4. Open the browser console: a CORS error on an image means the file is not served by your bucket host. Bucket hosts answer with `Access-Control-Allow-Origin: *` for reads.
