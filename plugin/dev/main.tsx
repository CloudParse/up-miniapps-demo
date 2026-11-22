// Development only: runs the plugin in a plain page, with a host that is a stand-in for the Studio.
//
// What it keeps: the real plugin code, hot reload, and the real calls to the demo API.
// What it does not: the sandbox, the Studio layout, the host styles. After a change,
// check the plugin once in the real Studio (docs/plugin.md, "Run it in the Studio").
import {
  ApiService,
  type PluginHost,
  type PluginPage,
} from "@cloudparse/up-backoffice-sdk";
import plugin from "@plugin/index";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

// The Hub's shared DEV registration of every mini-app (../miniapp/src/dev/devHub.ts).
const MOCK_APP_UUID = "0d0d0d0d-0000-4000-8000-000000000001";
// A DEV test user (development data, no real account). `?user=<number>` picks another
// one from ../miniapp/src/dev/devHub.ts. It must carry the mini-app administrator
// flag, or the API answers 403 to the admin routes.
const DEFAULT_USER = "639980001";
const TEST_PASSWORD = "password123";
const ADMIN_SCOPE = "profile:miniapp:admin";
const HUB = "/hub/api/v1";
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
    { scopes: [ADMIN_SCOPE] },
    master.token,
  );
  cached = { expiresAt: Date.now() + TOKEN_LIFETIME_MS, token: scoped.token };
  return scoped.token;
}

// The same class the Studio uses for `miniappApi`. The Vite server proxies /api/ to the API.
const miniappApi = new ApiService("/api/v1");
miniappApi.setTokenLoader(adminToken);

const host: PluginHost = {
  application: {
    httpBackendUrl: "/api/v1",
    iconUrl: null,
    name: "Demo mini-app (development)",
    uuid: MOCK_APP_UUID,
    wsBackendUrl: null,
  },
  basePath: "/",
  contractVersion: 1,
  getScopeToken: () => adminToken(),
  hubApi: new ApiService(""),
  miniappApi,
  navigate: (pagePath) => {
    window.location.hash = pagePath;
  },
  user: { admin: true, fullName: "Test user", uuid: MOCK_APP_UUID },
};

const style = document.createElement("style");
style.textContent = plugin.styles ?? "";
document.head.append(style);

function currentPage(): Omit<PluginPage, "component"> | undefined {
  const path = window.location.hash.replace(/^#/, "");
  return plugin.pages.find((page) => page.path === path) ?? plugin.pages[0];
}

const rootElement = document.getElementById("root");
if (!rootElement) throw new Error("#root is missing");
createRoot(rootElement).render(
  <StrictMode>
    <main className="mx-auto max-w-5xl p-8">
      {plugin.renderPage(currentPage()?.path ?? "", host)}
    </main>
  </StrictMode>,
);
