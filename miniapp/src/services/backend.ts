import { APP_CONFIG } from "@app/config/env";
import { createApiService } from "@cloudparse/up-miniapps-sdk";

// Backend URL precedence: the shell's env (live, via UPDATE_CONTEXT) first,
// then the build-time VITE_BACKEND_URL. Nothing is ever invented: when neither
// is set the app shows an explicit "not configured" state instead.
export const apiClient = createApiService({
  defaultBaseUrl: APP_CONFIG.backendUrl,
});

export function getBackendUrl(): string | null {
  const url = apiClient.baseUrl;
  return url.length > 0 ? url : null;
}

export function getWsUrl(): string | null {
  const url = apiClient.wsUrl;
  return url && url.length > 0 ? url : null;
}

export class BackendNotConfiguredError extends Error {
  constructor() {
    super(
      "Backend non configuré : la plateforme fournit l'adresse quand le backend est déployé, ou renseigne VITE_BACKEND_URL en développement.",
    );
    this.name = "BackendNotConfiguredError";
  }
}

export function requireBackendUrl(): string {
  const url = getBackendUrl();
  if (!url) throw new BackendNotConfiguredError();
  return url;
}

export function joinBackendPath(path: string): string {
  return `${requireBackendUrl().replace(/\/+$/, "")}/${path.replace(/^\/+/, "")}`;
}

export const apiService = {
  get: async <T>(path: string): Promise<T> => {
    requireBackendUrl();
    const response = await apiClient.get<T>(path);
    if (response.status < 200 || response.status >= 300) {
      throw new Error(`GET ${path} a échoué (${response.status})`);
    }
    return response.data;
  },
  post: async <T>(path: string, body: unknown): Promise<T> => {
    requireBackendUrl();
    const response = await apiClient.post<T>(path, body);
    if (response.status < 200 || response.status >= 300) {
      throw new Error(`POST ${path} a échoué (${response.status})`);
    }
    return response.data;
  },
};
