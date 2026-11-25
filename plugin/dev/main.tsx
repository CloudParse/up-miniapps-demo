// Development only: runs the plugin in a plain page, with a host that is a stand-in for the Studio.
//
// What it keeps: the real plugin code, hot reload, and the real calls to the demo API.
// What it does not: the sandbox and the Studio layout. It loads the Studio fonts (Figtree,
// Bricolage Grotesque) and the light page colours itself: the Studio gives them to the real frame.
// After a change, check the plugin once in the real Studio (docs/plugin.md, "Run it in the Studio").
import {
  ApiService,
  type PluginHost,
  type PluginPage,
} from "@cloudparse/up-backoffice-sdk";
import plugin from "@plugin/index";
import "@fontsource/figtree/latin-400.css";
import "@fontsource/figtree/latin-500.css";
import "@fontsource/figtree/latin-600.css";
import "@fontsource/figtree/latin-700.css";
import "@fontsource/figtree/latin-800.css";
import "@fontsource/figtree/latin-900.css";
import "@fontsource/bricolage-grotesque/latin-600.css";
import "@fontsource/bricolage-grotesque/latin-700.css";
import "@fontsource/bricolage-grotesque/latin-800.css";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { apiProblem, devBaseUrls, devWsUrl } from "./devHost";

// The Hub's shared DEV registration of every mini-app (../miniapp/src/dev/devHub.ts).
const MOCK_APP_UUID = "0d0d0d0d-0000-4000-8000-000000000001";
// A DEV test user (development data, no real account). `?user=<number>` picks another
// one from ../miniapp/src/dev/devHub.ts. It must carry the global Hub flag
// `miniapp_admin`, or the API answers 403 to the admin routes.
const DEFAULT_USER = "639980001";
const TEST_PASSWORD = "password123";
// The SDK's ApiService needs absolute base URLs (devHost.ts); the Vite server proxies /api/ and /hub/.
const urls = devBaseUrls(window.location.origin);
const HUB = urls.hubLogin;
// The token lives 5 minutes: renew it a minute early.
const TOKEN_LIFETIME_MS = 4 * 60 * 1000;

async function postJson<T>(
  url: string,
  body: unknown,
  token?: string,
): Promise<T> {
  const response = await fetch(url, {
    body: JSON.stringify(body),
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    method: "POST",
  });
  if (!response.ok) throw new Error(`${url}: HTTP ${response.status}`);
  return (await response.json()) as T;
}

let cached: { expiresAt: number; token: string } | null = null;

async function adminToken(): Promise<string> {
  if (cached && cached.expiresAt > Date.now()) return cached.token;
  const localNumber =
    new URLSearchParams(window.location.search).get("user") ?? DEFAULT_USER;
  const master = await postJson<{ token: string }>(`${HUB}/auth/login`, {
    countryCode: "+33",
    localNumber,
    password: TEST_PASSWORD,
  });
  const scoped = await postJson<{ token: string }>(
    `${HUB}/applications/${MOCK_APP_UUID}/token`,
    // Empty body: the Hub adds the admin scope on its own when the user has the
    // global Hub flag `miniapp_admin`.
    {},
    master.token,
  );
  cached = { expiresAt: Date.now() + TOKEN_LIFETIME_MS, token: scoped.token };
  return scoped.token;
}

// The same class the Studio uses for `miniappApi`. The Vite server proxies /api/ to the API.
const miniappApi = new ApiService(urls.api);
miniappApi.setTokenLoader(adminToken);

const host: PluginHost = {
  application: {
    httpBackendUrl: urls.api,
    iconUrl: null,
    name: "Demo mini-app (development)",
    uuid: MOCK_APP_UUID,
    // Like the Studio: the registered WebSocket address of the mini-app (here the same origin, through the Vite proxy).
    wsBackendUrl: devWsUrl(urls.api),
  },
  basePath: "/",
  contractVersion: 1,
  getScopeToken: () => adminToken(),
  hubApi: new ApiService(urls.hub),
  miniappApi,
  navigate: (pagePath) => {
    window.location.hash = pagePath;
  },
  user: { admin: true, fullName: "Test user", uuid: MOCK_APP_UUID },
};

const style = document.createElement("style");
style.textContent = plugin.styles ?? "";
document.head.append(style);
// The light Studio page: the same background, text colour and font as the real frame.
document.body.className =
  "m-0 min-h-screen bg-background font-sans text-foreground antialiased";

function currentPage(): Omit<PluginPage, "component"> | undefined {
  const path = window.location.hash.replace(/^#/, "");
  return plugin.pages.find((page) => page.path === path) ?? plugin.pages[0];
}

const rootElement = document.getElementById("root");
if (!rootElement) throw new Error("#root is missing");
const problemBox = document.createElement("div");
problemBox.setAttribute("role", "alert");
problemBox.style.cssText =
  "display:none;margin:16px auto;max-width:64rem;padding:12px 16px;border-radius:8px;background:#fef2f2;color:#991b1b;font:14px sans-serif";
rootElement.before(problemBox);
// Checked again every few seconds: the message goes away when the API starts.
async function refreshProblem(): Promise<void> {
  const problem = await apiProblem(urls.api);
  problemBox.textContent = problem ?? "";
  problemBox.style.display = problem ? "block" : "none";
}
void refreshProblem();
setInterval(() => void refreshProblem(), 4000);

createRoot(rootElement).render(
  <StrictMode>
    <main className="mx-auto max-w-5xl p-8">
      {plugin.renderPage(currentPage()?.path ?? "", host)}
    </main>
  </StrictMode>,
);
