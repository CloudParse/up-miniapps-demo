# plugin/AGENTS.md: Studio plugin (`up-miniapps-demo-plugin`)

Read the root `AGENTS.md` first (security rules, review). Guide with the commands, the dev page and the publishing: `docs/plugin.md`. This file covers the plugin only.

## What the plugin is for

The plugin is the admin page of the mini-app, in the Studio. Most often, the admins use it to put data into the mini-app's database: content (events, places, products, categories), settings, moderation. For each kind of data: an admin route in `api/`, a service in `src/services/`, a page with a `Table` and a create/edit `Modal` in `src/features/`. The plugin never writes to the database itself. Details: `docs/plugin.md`, "What a plugin is for".

## Stack and commands

React 19, TypeScript (strict), Vite, Tailwind CSS v4, Biome, `@cloudparse/up-backoffice-sdk`. Node.js 26 LTS.

```bash
npm ci
npm run dev                                          # development page, port 21516
npm run check:write && npm run typecheck && npm run build   # dist/plugin.js
```

## Rules

- `src/index.tsx` default-exports `definePlugin({ id, name, pages, styles })`. The `id` is lowercase. Rename the template's `up-miniapps-demo` to your mini-app's own id: two mini-apps made from the template would publish the same one.
- Light Studio theme and Studio fonts by default (Figtree, Bricolage Grotesque through `font-display`). Never a dark theme, never another font.
- Your own markup follows the Studio look of the SDK components (`up-backoffice-plugin-builder`, `references/sdk-api.md`, section "Studio look"): mixed case, no `uppercase`, `font-black` or `tracking-widest`, the `field` utility on hand-written inputs and selects, `rounded-card` cards, no height or radius on a `Button`.
- This is Studio code, not mini-app code. Use the SDK UI kit (`SectionHeader`, `StatTile`, `Table`, `Modal`, `Banner`, ...), English text, Tailwind theme tokens (the light Studio theme comes from the SDK 0.3.0, `src/styles.css` only imports it; no `white/…` or `black/…` opacity classes, no hard-coded colors), no arbitrary values, no `any`. No `alert`, `confirm`, `window.open`, cookies or web storage: the plugin runs in a sandboxed iframe.
- No `<form>` element and no `type="submit"` button. The iframe is sandboxed without `allow-forms`, so the browser blocks the submission before `onSubmit` runs. Use a `<div>`, `ModalActions submitType="button" onSubmit={handleSubmit}` and `type="button"` buttons with `onClick`. The development page has no sandbox and does not show this bug.
- API calls only through `miniappApi` (`src/services/`). Paths start after the API base URL, which ends with `/api/v1`. Check errors with `isApiError()`, never `instanceof ApiError`.
- The plugin never holds a database, cache or bucket credential, and nothing secret: everything goes through an admin route of `api/`.
- Production output: ONE ES module, `dist/plugin.js` (`plugin` section of `miniapp.yaml`). No code splitting, no dynamic `import()`. `grep -c __UP_BACKOFFICE_SHARED__ dist/plugin.js` must print 3.
- `dev/`, `index.html` and `vite.dev.config.ts` are the development page only. Never import them from `src/`.
- `src/features/demo/`, `src/services/demo.ts` and the API routes `admin/demo/*` are the example: replace them with your own pages and routes. The page "Notes" (`NotesPage.tsx`, `NoteModal.tsx`, `POST /api/v1/admin/demo/notes`) is the plugin pattern to copy when admins put data into the database. On the API side, use `models/` and `repositories/` (`api/AGENTS.md`), not raw SQL in a service like the demo.
- Realtime: `src/lib/realtimeClient.ts` (reconnect with backoff, ticket, ping), `src/hooks/useRealtime.ts` and `src/features/demo/RealtimeStatus.tsx` keep a WebSocket to the API and show its state ("Realtime: connected / reconnecting / offline"). The address is `usePluginHost().application.wsBackendUrl`. A page that shows data the mini-app changes should use the hook, update from the event and read the data again from the API when the socket opens. Contract of the events: `docs/realtime.md`. Tests: `npm test` (`dev/realtime.test.ts`).
