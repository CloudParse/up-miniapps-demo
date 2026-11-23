---
name: up-miniapp-web-launcher
description: How the Up website (web launcher) shows a mini-app. Phone mock and device picker on a computer, fullscreen on a phone, what the web host supports, where the backend addresses come from, and how to test as a member. Use when a feature must work on the website, when a capability answers "not supported by the UP web host", or when the backend address is missing.
---

# Up web launcher

Status: draft. Source of truth: `docs/web-launcher.md`. Last audited 2026-11-23.

Read `docs/web-launcher.md` first. This skill is the checklist.

## Display

- The SDK pinned in `miniapp/package.json` must be `@cloudparse/up-miniapps-sdk` 0.17.0 or newer. An older SDK draws no phone mock.
- Do not draw your own phone frame. `<SDKProvider>` reads `window.__UP_RENDER_AS__` and does it.
- A computer shows the mock with a device picker. A phone, or a narrow window of any browser, shows the app fullscreen, with a **Plein écran** button where the Fullscreen API exists (not in Safari on iPhone: use Add to Home Screen). The exit button is `sdk.ui.exit()`.
- Layout height is `h-full` or `100%`, never `100vh`.

## What the web host supports

- Works: initialize, context, profile, network, storage and secure storage (memory, per tab), permission request, exit.
- Accepted, no effect: debug log, scroll config, system bars, haptics.
- Not supported: fidelity, location, camera and QR scan, media, payment, achievements, routing, navigation, activity. The answer is `<REQUEST> is not supported by the UP web host`.
- For each capability you use, decide what the person sees on the website. Use `getErrorMessage` (`miniapp/src/lib/errors.ts`) so the message is clear and in French.

## Backend addresses

- Never write an address in the code. Use `createApiService` and `createWsService` of the SDK.
- Order: `window.__UP_BACKEND_URLS__`, then `sdk.getEnv()`, then an `UPDATE_CONTEXT` event.
- If the screen shows "Backend non configuré", the backend is not deployed yet or no address is registered. Deploy the backend from the Studio and wait: the launcher asks again every 8 seconds for 10 minutes.
- Convention: `https://api.<mini-app>.app.<domain>/api/v1` and `wss://api.<mini-app>.app.<domain>/api/v1/ws`.

## Test

1. Deploy the frontend and the backend from the Studio.
2. Open the website as a member (not as an admin).
3. Try two devices on a computer. Check the exit button.
4. Read the browser console. A CORS error on an image or a font is a hosting problem, not a code problem.

## Never

- Never add `allow-same-origin` thinking, or code, that needs the website's cookies or storage. The frame is sandboxed on purpose.
- Never put a token or a secret in `window`, in the URL or in a bundle.
