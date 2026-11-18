// Development only: sign in to the organisation's DEV backend (the "Hub") as one
// of its test users, then get the scoped token the shell would give this mini-app.
// Cut out of a production build: App.tsx guards it with the literal import.meta.env.DEV.
//
// The DEV backend seeds the same registration and the same users (up/backend,
// DEV seed Job of story 024). Keep both lists identical.

// Shared by every mini-app in development: the DEV backend registers it once.
export const MOCK_APP_UUID = "0d0d0d0d-0000-4000-8000-000000000001";

// `import.meta.env.DEV` is read here on purpose (the rest of the app reads env in
// config/env.ts only): the literal lets the production build drop the list and
// the password entirely.
const DEV = import.meta.env.DEV;

// Same password for every test user (development data, no real account).
const TEST_PASSWORD = DEV ? "password123" : "";

export interface TestUser {
  firstName: string;
  lastName: string;
  // French local number, country code +33.
  localNumber: string;
}

export const TEST_USERS: readonly TestUser[] = DEV
  ? [
      { firstName: "Camille", lastName: "Martin", localNumber: "639980001" },
      { firstName: "Lucas", lastName: "Bernard", localNumber: "639980002" },
      { firstName: "Inès", lastName: "Dubois", localNumber: "639980003" },
      { firstName: "Hugo", lastName: "Thomas", localNumber: "639980004" },
      { firstName: "Léa", lastName: "Robert", localNumber: "639980005" },
      { firstName: "Nathan", lastName: "Richard", localNumber: "639980006" },
      { firstName: "Chloé", lastName: "Petit", localNumber: "639980007" },
      { firstName: "Yanis", lastName: "Durand", localNumber: "639980008" },
      { firstName: "Manon", lastName: "Leroy", localNumber: "639980009" },
      { firstName: "Adam", lastName: "Moreau", localNumber: "639980010" },
      { firstName: "Sarah", lastName: "Simon", localNumber: "639980011" },
      { firstName: "Louis", lastName: "Laurent", localNumber: "639980012" },
      { firstName: "Jade", lastName: "Lefebvre", localNumber: "639980013" },
      { firstName: "Gabriel", lastName: "Michel", localNumber: "639980014" },
      { firstName: "Zoé", lastName: "Garcia", localNumber: "639980015" },
    ]
  : [];

// The Vite dev server proxies /hub/ to the DEV backend (vite.config.ts).
const HUB = "/hub/api/v1";

const STORAGE_KEY = "up-demo-dev-user";

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
  if (!response.ok) {
    throw new Error(`${url}: HTTP ${response.status}`);
  }
  return (await response.json()) as T;
}

// The token the shell gives this mini-app for `user`: valid 5 minutes.
export async function scopedTokenFor(user: TestUser): Promise<string> {
  const master = await postJson<{ token: string }>(`${HUB}/auth/login`, {
    countryCode: "+33",
    localNumber: user.localNumber,
    password: TEST_PASSWORD,
  });
  const scoped = await postJson<{ token: string }>(
    `${HUB}/applications/${MOCK_APP_UUID}/token`,
    {},
    master.token,
  );
  return scoped.token;
}

export function savedUser(): TestUser | null {
  try {
    const number = window.sessionStorage.getItem(STORAGE_KEY);
    return TEST_USERS.find((user) => user.localNumber === number) ?? null;
  } catch {
    return null;
  }
}

export function saveUser(user: TestUser | null): void {
  try {
    if (user) {
      window.sessionStorage.setItem(STORAGE_KEY, user.localNumber);
    } else {
      window.sessionStorage.removeItem(STORAGE_KEY);
    }
  } catch {
    // Storage blocked: the choice lasts until the page reloads.
  }
}
