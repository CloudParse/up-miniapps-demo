# up-miniapps-react-template/AGENT.md: frontend (`up-miniapps-react-template`)

Read the root `AGENT.md` first (architecture, security rules, mandatory final review). This file covers the frontend only.

## Stack

React 19, TypeScript (strict), Vite, Tailwind CSS v4, Jotai, Biome, and the CloudParse SDK [`@cloudparse/up-miniapps-sdk`](https://www.npmjs.com/package/@cloudparse/up-miniapps-sdk). The font is Outfit (`@fontsource-variable/outfit`), the brand typeface of every Up surface.

```bash
npm install
cp .env.template .env      # VITE_BACKEND_URL points at the backend
npm run dev                # http://localhost:21515, runs in the SDK phone simulator
npm run check:write        # Biome: format + lint + organise imports
npm run typecheck
npm run build              # up-sdk build: ONE self-contained dist/index.html
```

## How a mini-app talks to Up

A mini-app is a web page loaded in a WebView inside the Up shell. It never talks to the phone or to Up directly: everything goes through the **SDK bridge** (`sdk`), which sends messages to the shell and receives events back.

Outside the shell (your browser), `SDKProvider` mounts a **simulator**: a phone frame with mock answers, so you develop without a phone. Inside the shell it does nothing.

### Boot sequence (already wired in `src/App.tsx`, keep it)

1. Wrap the whole tree in `<SDKProvider>`.
2. Call `sdk.initialize({ isDark: true })` once. The answer carries `insets` (safe areas) and `env` (including the backend URL the Hub registered for your app). Pass `isDark` here, not in a later update.
3. Store the answer in `contextAtom`. Merge later `GlobalEvent.UPDATE_CONTEXT` pushes into it; never replace it (the push is partial).
4. Listen to `UIEvent.BACK_GESTURE`: close the most specific open UI first, ask for exit confirmation last, then `sdk.ui.exit()`.
5. A failed boot ends in a visible `ErrorScreen` with a retry and an exit path. Never a silent spinner.

### Using the SDK

| Need | Use |
| --- | --- |
| Start up, safe areas, theme | `sdk.initialize`, `contextAtom`, `AppShell`, `TopBar` |
| Call your backend | `createApiService` (see `src/services/apiService.ts`). It resolves the backend URL live and routes through the shell, which attaches the user's token. Never hand-roll `fetch`, never store the URL in a constant. |
| User, storage, location, maps, haptics, payments... | `sdk.user`, `sdk.storage`, `sdk.haptic`, ... The README capability reference lists every method with its signature. |
| Leave the app | `sdk.ui.exit()`, always behind `ExitConfirmModal` |
| Shared UI | `BackButtonControl` and the other components the SDK exports. Check the SDK before writing a component it already provides. |

Look signatures up in the SDK README or its `.d.ts`; never guess a method name.

## Resources: read these while you build

- **Storybook** (live demos of every SDK component and capability): [SDK README, "Storybook" section](https://www.npmjs.com/package/@cloudparse/up-miniapps-sdk?activeTab=readme#storybook). It is part of the SDK repository (`npm run storybook`, `http://localhost:6006`); stories are grouped by area (`lifecycle`, `location`, `map`, `storage-network`, `ui-kit`, ...).
- **Claude Code plugin / skill** (SDK reference, tested recipes, mandatory mini-app rules, `/new-miniapp` scaffold): [SDK README, "Claude Code plugin" section](https://www.npmjs.com/package/@cloudparse/up-miniapps-sdk?activeTab=readme#claude-code-plugin). Its `up-miniapp-builder` skill loads whenever you work on a mini-app and points at exact signatures. It ships inside the npm package: install it from `node_modules/@cloudparse/up-miniapps-sdk/claude-plugin` (step 4 of the root `SETUP.md`); reinstall it after every SDK upgrade.
- **Showcase app**: a complete mini-app exercising every SDK capability, the best source of working examples.
- All package versions: [npm versions page](https://www.npmjs.com/package/@cloudparse/up-miniapps-sdk?activeTab=versions).

## Structure

```text
src/
├── main.tsx            entry: styles + <App />
├── App.tsx             SDKProvider, boot, back gesture, top-level layout (no feature logic)
├── atoms/              app-wide state: boot, context, overlay
├── config/env.ts       the ONLY reader of import.meta.env
├── components/
│   ├── layout/         AppShell, TopBar, SplashScreen, ErrorScreen, ExitButton, AuroraBackground
│   ├── modals/         ConfirmModal (generic) and the modals built on it
│   └── ui/             generic primitives: Button, Dialog, SkeletonBlock
├── features/<name>/    one folder per feature
│   ├── <Name>Screen.tsx   composition only
│   ├── atoms.ts           the feature's state and its action atoms
│   ├── types.ts           IBackend<Entity> (wire) and <Entity> (UI)
│   └── components/        the feature's own components
├── hooks/              reusable hooks (useSdkEvent)
├── lib/                pure helpers (cn, errors, layout, store)
├── services/           network layer: apiService + one service per backend resource
└── styles/index.css    Tailwind, theme tokens, font
```

### Adding a feature

1. `features/<name>/types.ts`: the wire interface `IBackend<Entity>` and the UI type.
2. `services/<name>Service.ts`: calls `apiService` and maps wire to UI in one `mapBackend<Entity>` function. This is the only place wire shapes exist.
3. `features/<name>/atoms.ts`: state as a discriminated union (`loading | ready | error`) plus a write-only action atom that runs the request.
4. `features/<name>/components/`: small presentational components, one responsibility each.
5. `features/<name>/<Name>Screen.tsx`: reads atoms, triggers the action, composes components.
6. Mount the screen in `App.tsx`.

`features/hello/` is the worked example: read it before writing your own.

## Component rules

- **No monolithic components.** If a component mixes data loading, layout and several visual blocks, split it. Rule of thumb: more than ~80 lines, or more than one reason to change.
- **Screens compose, components render.** A screen wires atoms to components; a component receives props and returns markup.
- **Extract reusable pieces** (a badge, a card, a skeleton) the second time you need them, into `components/ui/` if generic, or the feature's `components/` if specific.
- Props are a named, exported `interface FooProps`. No `React.FC`.
- A loading state is a **skeleton with the loose shape of the content**, not a spinner. Every failure has a visible error state with a retry.
- Prefer a component the SDK already exports over a local copy.

## Code conventions

- **State is Jotai**: one atoms file per domain, no `<Provider>` (the default store is shared, `lib/store.ts` reaches it outside React). Local `useState` only for UI-only state of one component.
- **Styling is Tailwind with theme tokens.** Colors and sizes come from the `@theme` tokens in `styles/index.css` (`bg-brand-card`, `text-ink-soft`, `text-md-plus`): no hex values in components. If you add a custom token, register it in `lib/utils.ts` (`extendTailwindMerge`) or `cn()` will silently drop classes.
- **Touch-only WebView**: no `hover:`, `active:`, `focus:` variants.
- **Layout**: `h-full`, never `h-screen` / `100dvh` (the simulator mounts the app in a scaled box). Apply `insets` through `AppShell` and `TopBar`.
- `unknown`, never `any`. Type responses with real interfaces; narrow `catch (error)` values.
- Never `window.alert` / `confirm`: use the `Dialog`-based modals.
- Never render backend or user text as HTML.
- Environment variables: declare in `vite-env.d.ts` and `.env.template`, read only in `config/env.ts`. Dev-only values are blanked when `import.meta.env.PROD`.
- Imports use the `@app/*` alias. Biome sorts imports and keys: run `npm run check:write` before committing.
- Add a dependency only when the SDK, React or the platform cannot do the job.

## Definition of done

`npm run check`, `npm run typecheck` and `npm run build` pass, then the **mandatory final review** of the root `AGENT.md` (section 7) is done, with the frontend points in mind: no secret in the bundle, no monolithic component, reusable pieces extracted, no dead code.
