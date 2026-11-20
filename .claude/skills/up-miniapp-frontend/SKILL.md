---
name: up-miniapp-frontend
description: Frontend guide for miniapp/. Stack, folders, Jotai state (atoms, LoadState, loaders), services, components, Tailwind tokens, SDK boot, WebView rules and frontend security. Use before writing or reviewing any code under miniapp/.
---

# Up mini-app frontend

How to use this skill:
- `miniapp/AGENT.md` holds the rules. This skill shows how to apply them.
- Copy the patterns of this repository. Do not invent a new one.
- SDK signatures: the SDK README, its `.d.ts`, or the skill `up-miniapp-builder` of the SDK plugin. Never guess a method name.

## 1. Stack

- React 19, TypeScript `strict`, Vite, Tailwind CSS v4, Jotai, Biome, lucide-react icons, Radix primitives (`radix-ui`).
- `@cloudparse/up-miniapps-sdk`: the bridge to the shell, the simulator, shared components and `up-sdk build`.
- Imports use the `@app/*` alias.
- UI text is French. Code and comments are English.
- `npm run build` runs `up-sdk build`: one self-contained `dist/index.html`.

## 2. Where code goes

```text
src/
├── App.tsx        SDKProvider, boot gate, back-gesture ladder, tabs, exit modal
├── config/        env.ts (reads import.meta.env, see section 8), tabs, demo data
├── atoms/         one file per domain, LoadState atoms
├── services/      one file per backend resource: wire type, mapping, fetch
├── features/<area>/  screens, their small components, their loader functions
├── components/ui/      Button, Card, Badge, Input, Switch, Skeleton, Dialog, SegmentedControl
├── components/layout/  AppShell, TopBar, BottomNav, ExitButton, OverlayInteractive, SplashScreen, ErrorScreen, EmptyState, ScreenTitle
├── components/modals/  ConfirmModal
├── hooks/         useAction (button state), useSdkEvent (event subscription)
├── lib/           cn(), errors, loadState, layout, store
├── utils/constants/  brand.ts: token values needed outside className
├── dev/           development only: test-user sign-in (cut from production builds)
└── styles/index.css  @theme tokens, dark and light
```

Dependencies go one way: `features` use `components`, `atoms`, `services`, `hooks`, `lib`. A service never imports a component. A `ui` component never imports a feature.

## 3. State with Jotai

Rules:
- One store: the implicit default store. No Jotai `Provider`.
- Code outside React (loaders, SDK handlers) uses `appStore` from `lib/store.ts`.
- One atoms file per domain in `atoms/`.
- Remote data is a `LoadState<T>`: `idle | loading | ready | error`.
- Derived state is a read-only `atom((get) => ...)`. Never keep a copy in sync by hand.
- A loader function loads the data once per session. Only a pull-to-refresh or a retry loads it again.
- Local UI state (an open sheet, a text field) stays in `useState`.

The pattern, from the repository:

```ts
// lib/loadState.ts
export type LoadState<T> =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ready"; data: T }
  | { status: "error"; message: string };

// atoms/greeting.ts
export const greetingAtom = atom<LoadState<Greeting>>({ status: "idle" });

// features/home/greetingLoader.ts
export async function loadGreeting(force = false): Promise<void> {
  if (!force && appStore.get(greetingAtom).status === "ready") return;
  appStore.set(greetingAtom, { status: "loading" });
  try {
    appStore.set(greetingAtom, { data: await fetchGreeting(), status: "ready" });
  } catch (error) {
    appStore.set(greetingAtom, { message: getErrorMessage(error), status: "error" });
  }
}
```

Read with `useAtomValue`, write with `useSetAtom`. Use `useAtom` only when the component does both.

## 4. Services (calling the API)

- `services/backend.ts` builds the one client with `createApiService`. The URL is the shell's `env.backendUrl`, else `VITE_BACKEND_URL`.
- The shell attaches the user's token. Never call `fetch` by hand. Only `src/dev/` does, for the test-user sign-in.
- One file per resource. It holds the wire type (`IBackend...`), the UI type and one mapping function.
- No other file maps wire data.

```ts
// services/helloService.ts
interface IBackendGreeting { message: string; }
export interface Greeting { message: string; }

function mapBackendGreeting(greeting: IBackendGreeting): Greeting {
  return { message: greeting.message };
}

export async function fetchGreeting(): Promise<Greeting> {
  return mapBackendGreeting(await apiService.get<IBackendGreeting>(HELLO_PATH));
}
```

A missing backend URL shows a visible empty state. Never invent a URL.

## 5. Components

Rules:
- Small components. A screen composes parts. Split a component as soon as it has two jobs.
- Props: a named, exported `interface FooProps`. No `React.FC`.
- Types: `unknown`, never `any`.
- Reuse `components/ui` and `components/layout` before writing a new primitive.
- Move a piece to `components/` as soon as a second screen needs it.
- Every remote state renders loading (`Skeleton`), ready and error (the message and "Réessayer"). A list also renders its empty case (`EmptyState`).
- Buttons that run an async call use `useAction`: it gives `idle | pending | success | error`.
- SDK events go through `useSdkEvent`. It subscribes once and unsubscribes on unmount.

Example (`features/home/BackendGreetingCard.tsx`):

```tsx
export function BackendGreetingCard() {
  const greeting = useAtomValue(greetingAtom);
  useEffect(() => { void loadGreeting(); }, []);

  return (
    <Card className="flex flex-col gap-2">
      {greeting.status === "ready" ? (
        <p className="font-display text-md-plus font-semibold text-ink-bright">{greeting.data.message}</p>
      ) : greeting.status === "error" ? (
        <div className="flex flex-col gap-2">
          <p className="text-xs-plus text-accent-danger">{greeting.message}</p>
          <Button onClick={() => void loadGreeting(true)} size="sm" variant="secondary">Réessayer</Button>
        </div>
      ) : (
        <SkeletonBlock className="h-6 w-40" />
      )}
    </Card>
  );
}
```

Adding a feature:
1. Service in `services/` (wire type, mapping, fetch).
2. Atom in `atoms/` and a loader in `features/<area>/`.
3. Screen and small components in `features/<area>/`, built from `ui` and `layout`.
4. Expose it from a tab (`config/tabs.ts`) or a tool sub-page.
5. `npm run check:write && npm run typecheck && npm run build`, then walk the path in the simulator.

## 6. Styling

- Colours and sizes come from the `@theme` tokens of `styles/index.css` (`text-ink-bright`, `bg-brand-panel`, `text-md-plus`...). No hex values, no bracket sizes in components.
- A new token is also registered in `lib/utils.ts` (`extendTailwindMerge`), or `cn()` drops the class.
- A token value needed outside `className` (a map colour, a canvas) is mirrored in `utils/constants/brand.ts`.
- Fonts: Figtree (`font-sans`, default). Bricolage Grotesque (`font-display`) for display text only: screen and section titles, card headlines, dialog titles, avatar initials.
- Dark and light through `[data-theme]`. Test both.
- Keep `@source "../../node_modules/@cloudparse/up-miniapps-sdk/dist"` in `styles/index.css`.

## 7. Rules of the phone WebView

- **Boot** (`App.tsx`, keep it):
  1. Wrap the tree in `SDKProvider`.
  2. Call `sdk.initialize({ isDark })` once. Store the answer in `contextAtom`.
  3. Merge each later `GlobalEvent.UPDATE_CONTEXT` with `mergeShellContext`. Never replace the context: the push is partial.
  4. Call `sdk.config({ routingBackend })`.
  5. A failed boot shows `ErrorScreen` with a retry and an exit.
- **Back gesture**: `UIEvent.BACK_GESTURE` closes an overlay, then a sub-page, then goes to the home tab, then opens the exit modal.
- **Exit**: `ExitButton` opens the SDK `ExitConfirmModal`. Only its confirm calls `sdk.ui.exit()`.
- **Insets**: each bar applies its own edge (`TopBar` top, `BottomNav` bottom). `AppShell` applies left and right only.
- **Height**: `h-full`, never `h-screen` or `100dvh`.
- **Dialogs and sheets** portal into `usePhoneContainer()` of the SDK. Centre them with `left-1/2 top-1/2` and a translate. Never `document.body`, never a viewport unit.
- **Touch only**: no `hover:`, `focus:` or `active:` variants.
- **No `window.alert` or `confirm`**: use `Dialog` or `ConfirmModal`.
- **QR codes**: `sdk.qrCode.generate` through `features/media/qrCodeCache.ts`.
- **Payment**: enabled only in the simulator (`useIsMocked`). A real request charges a card.

## 8. Security

- Everything in `miniapp/` is public. `VITE_*` values are inlined in the bundle: never a key, token or secret.
- `import.meta.env` is read only in `config/env.ts`. Two exceptions read `import.meta.env.DEV`: `src/dev/devHub.ts` and `App.tsx` (the guard of the test-user picker).
- Dev-only values are blanked when `import.meta.env.PROD`.
- Never render backend or user text as HTML. No `dangerouslySetInnerHTML`.
- Never build a URL from user or backend input without validating it (`https:` only, known host).
- Never store a token yourself. The shell owns it.
- Add a dependency only when the SDK, React or the platform cannot do the job. Run `npm audit` before shipping.

## 9. Done means

1. `npm run check:write`, `npm run typecheck`, `npm run build` pass.
2. The golden path works in the simulator, in dark and light.
3. The mandatory final review of the root `AGENT.md` (section 7) is done and its findings fixed.
