import { APP_CONFIG } from "@app/config/env";
import {
  createApiService,
  type INetworkResponse,
} from "@cloudparse/up-miniapps-sdk";

// The backend URL is resolved live on every call (shell-injected value first,
// then this fallback), so it is never stored in a module-level constant.
const api = createApiService({ defaultBaseUrl: APP_CONFIG.backendUrl });

function unwrap<T>(response: INetworkResponse<T>): T {
  if (response.status < 200 || response.status >= 300) {
    // The response body is deliberately left out: it may echo server details.
    throw new Error(`The backend answered with status ${response.status}.`);
  }
  return response.data;
}

export const apiService = {
  get: async <T>(path: string): Promise<T> => unwrap(await api.get<T>(path)),
};
