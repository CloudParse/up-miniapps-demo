# miniapp/AGENT.md: mini-app (`up-miniapps-demo-miniapp`)

Read the root `AGENT.md` first (architecture, security rules, mandatory final review). This file covers the mini-app only.

## Stack

- React 19, TypeScript (strict), Vite, Tailwind CSS v4, Jotai, Biome, MapLibre (`maplibre-gl`, `@vis.gl/react-maplibre`).
- The CloudParse SDK [`@cloudparse/up-miniapps-sdk`](https://www.npmjs.com/package/@cloudparse/up-miniapps-sdk) `^0.16.0`.
- Typography: the SDK stylesheet ships the Up font pair. Figtree is the UI font (`font-sans`, the default). Bricolage Grotesque is for display text only (`font-display`: screen titles, section titles, card headlines, dialog titles, avatar initials).
- Node.js 26 LTS (the SDK declares `engines.node >=26`).

```bash
npm install
cp .env.template .env      # VITE_BACKEND_URL=/api/v1, proxied by Vite to the API on 127.0.0.1:21514
npm run dev                # http://localhost:21515, runs in the SDK phone simulator (pick a test user)
npm run check:write        # Biome: format + lint + organise imports
npm run typecheck
npm run build              # up-sdk build: ONE self-contained dist/index.html
```

## How a mini-app talks to Up

A mini-app is a web page loaded in a WebView inside the Up shell. It never talks to the phone or to Up directly: everything goes through the **SDK bridge** (`sdk`), which sends messages to the shell and receives events back.

Outside the shell (your browser), `SDKProvider` mounts a **simulator**: a phone frame with mock answers, so you develop without a phone. Inside the shell it does nothing.

### Boot sequence (wired in `src/App.tsx`, keep it)

1. Wrap the whole tree in `<SDKProvider>`.
2. Call `sdk.initialize({ isDark })` once. The answer carries `insets` (safe areas) and `env` (including the backend URL the Hub registered for the app). Pass `isDark` here, never in a later `updateContext`.
3. Store the answer in `contextAtom`. Merge later `GlobalEvent.UPDATE_CONTEXT` pushes into it with `mergeShellContext`; never replace it (the push is partial).
4. Configure routing with `sdk.config({ routingBackend })` (OSRM), so journeys draw a route in the simulator.
5. Listen to `UIEvent.BACK_GESTURE` (`handleBack` in `App.tsx`): overlay, then tools sub-page, then home tab, then the exit modal.
6. A failed boot ends in a visible `ErrorScreen` with a retry and an exit path. Never a silent spinner.

### Calling the backend

- `src/services/backend.ts` builds the client with `createApiService`. The URL comes from the shell (`env.backendUrl`) first, then from `VITE_BACKEND_URL`. Never invent one: a missing backend shows a visible empty state.
- In development `VITE_BACKEND_URL` is `/api/v1`. `config/env.ts` turns a path into an absolute URL on the page's origin, and the Vite dev server forwards `/api/` to `http://127.0.0.1:21514` (`vite.config.ts`). An absolute URL is called directly.
- `vite.config.ts` `server.allowedHosts`: Vite answers only to known hosts. In a Coder workspace it allows exactly the port URL host of 21515, read from `VSCODE_PROXY_URI`. The shell variable `DEV_ALLOWED_HOSTS` adds hosts (Vite does not read it from `.env`). See `../docs/coder.md`.
- Requests go through the shell, which attaches the user's token. Never hand-roll `fetch`. The one exception is development tooling: `src/dev/` signs the simulator in as a DEV test user through the Vite proxy `/hub/` (`devHub.ts`), and is cut out of a production build (`import.meta.env.DEV` guards).
- Test users (development only): without `VITE_DEV_TOKEN`, the simulator first shows `DevUserPicker` (15 users of the DEV backend, `src/dev/devHub.ts`), then runs the app with the real scoped token of the one picked, renewed every 4 minutes (`useDevSession`). `DevUserSwitchCard` on the account screen goes back to the picker. `devHub.ts` reads `import.meta.env.DEV` itself so that the production build drops the list and the password.
- `src/services/helloService.ts` is the worked example: `GET /api/v1/hello`, wire type, mapping to the UI type in one function. `features/home/BackendGreetingCard.tsx` displays it, `features/home/greetingLoader.ts` loads it into `atoms/greeting.ts`.
- The realtime demo (`features/tools/RealtimeDemo.tsx`) needs a WebSocket URL from the shell. The demo backend has none, so the demo shows its "not configured" state locally.

Look signatures up in the SDK README or its `.d.ts`; never guess a method name.

## Resources: read these while you build

- **Storybook** (live demos of every SDK component and capability): [SDK README, "Storybook" section](https://www.npmjs.com/package/@cloudparse/up-miniapps-sdk?activeTab=readme#storybook).
- **Claude Code plugin** (SDK reference, tested recipes, mandatory mini-app rules, `/new-miniapp` scaffold): it ships inside the npm package. Install it from `node_modules/@cloudparse/up-miniapps-sdk/claude-plugin` (step 4 of the root `SETUP.md`); reinstall it after every SDK upgrade.
- All package versions: [npm versions page](https://www.npmjs.com/package/@cloudparse/up-miniapps-sdk?activeTab=versions).

## Structure

```text
src/
├── main.tsx            entry: SDK stylesheet (ships the Up fonts), Tailwind, maplibre worker
├── App.tsx             SDKProvider, boot gate, back-gesture ladder, tab shell, exit modal
├── config/             env.ts (the ONLY reader of import.meta.env), tabs, demo data (POIs, feature highlights)
├── atoms/              one Jotai atom file per domain (context, boot, navigation, account, greeting, map, eventLog)
├── lib/                cn() with registered tokens, errors, loadState, layout (top-bar floor), store
├── services/           backend (createApiService), helloService, accountService, shellContext merge
├── hooks/              useAction (button state), useSdkEvent (ref-stable subscription)
├── components/
│   ├── ui/             Button, Card, Badge, Input, Switch, Skeleton, Dialog, SegmentedControl
│   ├── layout/         AppShell, TopBar, ExitButton, BottomNav, SplashScreen, ErrorScreen, EmptyState, ScreenTitle
│   └── modals/         ConfirmModal (generic); ExitConfirmModal comes from the SDK
├── features/           one folder per tab: home, map, tools, media, account
├── styles/index.css    @theme tokens, dark/light via [data-theme]
└── assets/             local map styles (mapStyleDark.json, mapStyleLight.json), maplibre-gl-worker.bundled.js
scripts/generate-map-style.js   regenerates the two map styles from the CloudParse base style
```

### Adding a feature

1. Put the screen under `features/<area>/` and reuse the layout and ui primitives.
2. Requests go through `services/`: one service per backend resource, wire type and mapping to the UI type in that file only.
3. State that must survive tab switches goes in an atom in `atoms/`, as a `LoadState` (`idle | loading | ready | error`), loaded once by a loader function.
4. Expose it from a tab or a tool sub-page. Add a `FEATURE_HIGHLIGHTS` entry only for a headline feature.
5. Run `npm run check:write`, `npm run typecheck`, `npm run build`, then walk the golden path in the simulator.

## Rules

- **Insets**: each bar applies the inset of its own edge (`TopBar` with `topBarPaddingTop`, `BottomNav` with `insetBottom`), never the root. `AppShell` applies only left and right insets. The map screen is the one screen that goes fullscreen under both bars.
- **Map screen**: no push-down `TopBar` (`App.tsx` skips it on the map tab); it renders `<TopBar floating>`. Anything drawn over the map clears the measured header height (`headerClearance` in `MapScreen.tsx`), never a guessed constant.
- **Dialogs**: `components/ui/dialog.tsx` portals into `usePhoneContainer()` from the SDK and centres with `left-1/2 top-1/2` plus a translate. Never a viewport unit, never `document.body`.
- **Exit**: the top-left `ExitButton` opens the SDK's `ExitConfirmModal`; only its confirm calls `sdk.ui.exit()`. Sub-pages use a ChevronLeft back button.
- **Layout**: `h-full`, never `h-screen` or `100dvh` (the simulator mounts the app in a scaled box). Scrollbars are hidden app-wide.
- **Touch-only WebView**: no `hover:`, `focus:` or `active:` variants.
- **Tokens only**: colours and sizes come from the `@theme` tokens in `styles/index.css`. No hex values or bracket sizes in components. Mirror non-className values in `utils/constants/brand.ts`. A new token is registered in `lib/utils.ts` (`extendTailwindMerge`), or `cn()` silently drops the class.
- **SDK classes**: `styles/index.css` keeps `@source "../../node_modules/@cloudparse/up-miniapps-sdk/dist"`, so Tailwind generates the classes the SDK components use.
- **State**: Jotai, implicit default store (`lib/store.ts` reaches it outside React), one atoms file per domain, derived state as read-only `atom((get) => ...)`. Loads are cached in atoms once; only a pull-to-refresh forces a reload.
- **Props**: a named, exported `interface FooProps`. No `React.FC`. `unknown`, never `any`.
- **No `window.alert` / `confirm`**: use `Dialog` / `ConfirmModal`. Never render backend or user text as HTML.
- **Payment demo**: enabled only in the simulator (`useIsMocked`). A real payment request charges a card.
- **QR codes** go through `features/media/qrCodeCache.ts` (`sdk.qrCode.generate`), never a local QR library.
- **Environment variables**: declared in `src/vite-env.d.ts` and `.env.template`, read only in `config/env.ts` (exception: `src/dev/devHub.ts` reads `import.meta.env.DEV`, see above). Dev-only values are blanked when `import.meta.env.PROD`.
- **Imports** use the `@app/*` alias. Biome sorts imports and keys: run `npm run check:write` before committing.
- **Dependencies**: add one only when the SDK, React or the platform cannot do the job.
- **Language**: UI text is French. Code, identifiers and comments are English.

## Definition of done

`npm run check`, `npm run typecheck` and `npm run build` pass, then the **mandatory final review** of the root `AGENT.md` (section 7) is done, with the frontend points in mind: no secret in the bundle, no monolithic component, reusable pieces extracted, no dead code.
