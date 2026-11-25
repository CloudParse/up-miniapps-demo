# The Studio plugin (`plugin/`)

A plugin is the admin page of your mini-app. It is shown in the Studio (the organisation's administration site), in the "Plugin" tab of the mini-app. Admins use it to read or change the data of the mini-app.

The template ships a small working plugin. It shows the three things you need:
- how a page calls the API of the mini-app;
- how the plugin reaches PostgreSQL, the cache and the bucket (through the API);
- how the plugin is built, published and run in development.

Delete `plugin/` and the `plugin` section of `miniapp.yaml` if your mini-app has no admin page.

## What a plugin is for

Most often, the plugin is where the admins of the mini-app put data into its database. The mini-app's users only read that data, or react to it.

Examples:
- Content: events, places, products, articles, categories, tags. The admin creates, edits and deletes them in a table and a form.
- Settings: values the mini-app reads at run time (opening hours, limits, texts).
- Moderation: read what users posted, hide or delete it.
- Figures: counts and checks on the data, like the demo page.

The by-night mini-app works this way: its admins enter the establishments, events, tags and venue types in the plugin, and the app shows them.

How it works, for each kind of data:
1. An admin route of `api/` (`/api/v1/admin/...`, guard `require_admin`) reads or writes the table.
2. A service of the plugin (`plugin/src/services/`) calls that route with `miniappApi`.
3. A page of the plugin (`plugin/src/features/`) shows the rows in a `Table` and edits them in a `Modal`.

The demo plugin has two pages:
- "Resources": figures and one button (`DemoPage.tsx`).
- "Notes": the usual job of a plugin. A `Table` lists the rows of the table `demo_notes`. The modal "New note" writes one row through `POST /api/v1/admin/demo/notes` (`NotesPage.tsx`, `NoteModal.tsx`). Copy its plugin side (page, modal, service) for your own data. On the API side, store your own data through `models/` and `repositories/` (`api/AGENTS.md`), not with raw SQL in a service like the demo.

A real plugin usually also has an edit modal and a delete action per kind of data. The plugin never writes to the database itself: the API does.

## What a plugin is

- A folder of the repository: `plugin/`. Its own `package.json`, built with Vite and `@cloudparse/up-backoffice-sdk`.
- One ES module: `plugin/dist/plugin.js`. React comes from the Studio, everything else is bundled.
- It runs in a sandboxed iframe of the Studio. It has no cookie, no storage, no session and no secret. `window.open`, `alert` and `confirm` do not work: use the SDK components.
- A `<form>` does not work either. The iframe is sandboxed without `allow-forms`. The browser blocks the submission before `onSubmit` runs. The console shows `Blocked form submission to '' because the form's frame is sandboxed and the 'allow-forms' permission is not set.`

  Put the fields in a `<div>` and send the data from a button:

  ```tsx
  <ModalActions
    isSubmitting={saving}
    onCancel={close}
    onSubmit={handleSubmit}   // async () => { await myService.save(data) }, through miniappApi
    submitLabel="Save"
    submitType="button"       // the default "submit" needs a <form>
  />
  ```

  Every other action button is `type="button"` with an `onClick` handler.
- Its page code is Studio code, not mini-app code. Use the SDK UI kit, English text and no `any`.

| File | Role |
| --- | --- |
| `plugin/src/index.tsx` | `definePlugin({ id, name, pages, styles })`: the plugin and its pages. |
| `plugin/src/features/demo/DemoPage.tsx` | The page "Resources": three figures and one button. |
| `plugin/src/lib/realtimeClient.ts`, `src/hooks/useRealtime.ts`, `src/features/demo/RealtimeStatus.tsx` | The live figures: a WebSocket to the API with reconnection and a visible state. Events and flow: `docs/realtime.md`, "The plugin". |
| `plugin/src/features/demo/NotesPage.tsx`, `NoteModal.tsx` | The page "Notes": a table of the notes and the modal that writes one (no `<form>`, `ModalActions submitType="button"`). |
| `plugin/src/services/demo.ts` | The calls to the API (`miniappApi`). |
| `plugin/vite.config.ts` | The production build, `vite build` -> `dist/plugin.js`. |
| `plugin/vite.dev.config.ts`, `plugin/index.html`, `plugin/dev/main.tsx` | The development page (`npm run dev`). Not shipped. |

## 1. Call the routes of the API

The plugin calls the API with `miniappApi` from the SDK. The Studio runs the request:
- the base URL is the `httpBackendUrl` of the mini-app (it already ends with `/api/v1`, so paths start after it);
- the Studio adds an admin scoped token (`profile:miniapp:admin`);
- the plugin never sees the admin's session.

```ts
// plugin/src/services/demo.ts
export const demoService = {
  overview: () => miniappApi.get<DemoOverview>("/admin/demo/overview"),
  resetCache: () => miniappApi.post<DemoOverview>("/admin/demo/reset-cache"),
  listNotes: () => miniappApi.get<DemoNote[]>("/admin/demo/notes"),
  addNote: (text: string) =>
    miniappApi.post<DemoNote>("/admin/demo/notes", { text }),
};
```

Rules:
- Test an error with `isApiError(error)`, never `instanceof ApiError`.
- Never use `fetch` with a hard-coded URL.
- If the browser reports a CORS error in production, add the origin of the Studio to the API's `CORS_ALLOWED_ORIGINS` (`api/configs/config.toml`, `cors.allowed_origins`).

The demo routes are in `api/app/api/routes/demo.py` (`admin_router`):

| Route | Access | What it does |
| --- | --- | --- |
| `GET /api/v1/admin/demo/overview` | admin | Counts the rows of `demo_visits`, reads the cache counter, counts the objects under `demo/` in the bucket. |
| `POST /api/v1/admin/demo/reset-cache` | admin | Deletes the cache counter, returns the new overview. |
| `GET /api/v1/admin/demo/notes` | admin | The 50 newest rows of `demo_notes`. 503 when the database is not configured or does not answer. |
| `POST /api/v1/admin/demo/notes` | admin | `{"text": "..."}` (1 to 200 characters, trimmed): writes one row of `demo_notes`, answers 201 with it. 503 like `GET`. |

Like the rest of the demo, they are not served in production (404): the demo data is an example. A demo plugin deployed to production shows the warning "The demo routes are not served in production" instead of the figures. For your own plugin, add admin routes the way `api/app/api/routes/admin.py` does (the guard `require_admin` is declared once on the router).

## 2. PostgreSQL, the cache and the bucket: always through the API

The plugin has no database, cache or bucket credential, and it must never get one. The credentials stay in `api/.env` (workspace) or in the environment the platform gives the component (production).

```text
plugin ──miniappApi──▶ API (admin route) ──▶ PostgreSQL   DATABASE_URL
                                         ├──▶ cache        CACHE_URL, every key starts with CACHE_KEY_PREFIX
                                         └──▶ bucket       STORAGE_*
```

The code is `api/app/services/demo_admin_service.py`. It is a service that knows nothing about HTTP, like `demo_service.py`. The route only checks the admin scope and returns the result. A new need of the plugin is a new admin route and a new service method.

## 3. Publish the bundle

In the platform, open the mini-app and press **Déployer le plugin**. The workflow `.gitea/workflows/deploy-plugin.yml` runs on the runner of your organisation:

1. It checks the version (a plain semver, chosen by the platform) and reads `miniapp.yaml`.
2. It builds the plugin: the `plugin.build` command (`npm ci && npm run build`) in `plugin.dir`.
3. It copies `plugin/dist/plugin.js` (`plugin.out` and `plugin.file`) as `plugin-<version>.mjs`. The file must be one `.js` or `.mjs` module of at most 5 MB.
4. It publishes the file to the organisation API (`POST /admin/applications/<uuid>/backoffice-plugin/artifacts`) with a 15-minute session of this mini-app. The platform stores it in its private bucket under `backoffice-plugins/<mini-app uuid>/<version>-<artifact uuid>.js` and makes it the active version. It keeps the 5 newest versions.

The bucket of this step is the platform's, not the mini-app's own bucket (`STORAGE_*`). Details and the security model: `docs/deploy.md`. The `plugin` section of `miniapp.yaml` drives it:

```yaml
plugin:
  dir: plugin
  build: npm ci && npm run build
  out: dist
  file: plugin.js
```

Never change the workflow or the scripts (`AGENTS.md`, section 5.1).

## 4. Run the plugin in development

The Studio loads only published bundles: it cannot load a plugin from a development URL. The template gives you a small page that runs the same plugin code outside the Studio, with hot reload, against your API.

```bash
cd plugin
npm run dev          # terminal 3, port 21516
```

`dev-tools/up-dev.sh start plugin` from the root runs it in the background instead. `dev-tools/up-dev.sh start` runs the API, the mini-app and the plugin together.

Open it with the button **Plugin** of the Coder dashboard. The button works only while the plugin dev server runs (`npm run dev` in `plugin/`, or `dev-tools/up-dev.sh start`). Coder hides port 21516 from "Open ports" because the button exists. The button opens:

```text
https://plugin--<workspace>--<owner>--<organisation>.cloudparse.app
```

The page needs the API (terminal 1, port 21514) and the DEV backend. How it works:
- `plugin/vite.dev.config.ts` listens on `0.0.0.0` so Coder lists the port. It answers 403 to any Host header that is not the host of port 21516 (read from `VSCODE_PROXY_URI`), the host of the **Plugin** button (`plugin--<workspace>--<owner>--<org>...`), `DEV_ALLOWED_HOSTS` (comma separated) or a loopback name, IP addresses included. The guard is `dev-tools/hostGuard.ts`, shared with `miniapp/vite.config.ts`.
- It forwards `/api/` to the API on `127.0.0.1:21514` and `/hub/` to the DEV backend (`DEV_HUB_ORIGIN`).
- `plugin/dev/main.tsx` builds a stand-in for the Studio: the plugin's `miniappApi` is an `ApiService` with an admin scoped token for a DEV test user. It is development code and is not part of the bundle.

Limits:
- The admin routes need the scope `profile:miniapp:admin`. The DEV backend gives it only to a test user with the global Hub flag `miniapp_admin`. With another user, the page shows "The API refuses this account". Pick a user with `?user=<local number>` (the numbers are in `miniapp/src/dev/devHub.ts`). Ask an admin of your organisation to flag a test user if none is.
- The page has no sandbox and no Studio layout.
- Look once in the real Studio before you ship: press **Déployer le plugin**, then open the mini-app in the Studio, tab "Plugin".

Theme and fonts:
- A plugin is light by default, like the Studio. Never add a dark theme.
- The SDK components (0.4.0 and later) look like the Studio pages. Write your own markup the same way: mixed case, no `uppercase` or `font-black`, the `field` utility on hand-written inputs and selects, `rounded-card` cards, titles in `font-display font-bold text-title`. Details: section "Studio look" of `references/sdk-api.md` in the skill `up-backoffice-plugin-builder`.
- Its fonts are the Studio fonts: Figtree for text, Bricolage Grotesque for display titles (`font-display`). Never add another font.
- The backoffice SDK (0.3.0 and later) ships the palette and the font tokens. It ships no font file. `plugin/src/styles.css` only imports the SDK stylesheet.
- In the Studio, the fonts and the page background come from the Studio.
- On the development page, `plugin/dev/main.tsx` loads the same fonts (`@fontsource/figtree`, `@fontsource/bricolage-grotesque`, development only) and sets the same light background.
- A plugin built with an SDK older than 0.3.0 keeps the dark look. Update `@cloudparse/up-backoffice-sdk` to the latest release and rebuild.

## Checks

```bash
cd plugin
npm run check:write && npm run typecheck && npm run build
grep -c __UP_BACKOFFICE_SHARED__ dist/plugin.js    # 3: React comes from the Studio
```

SDK reference and recipes: the skill `up-backoffice-plugin-builder` of the SDK repository (`up/backoffice-sdk/claude-plugin`).
