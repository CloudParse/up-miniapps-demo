import { fileURLToPath } from "node:url";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import {
  appButtonHosts,
  devAllowedHosts,
  hostGuard,
} from "../dev-tools/hostGuard";

// Development only (`npm run dev`): a small page, index.html, that runs the plugin outside
// the Studio. It is NOT the production build (vite.config.ts): React is bundled here,
// the Studio supplies its own.
const DEV_PORT = 21516;
// The slug of the Coder app "Plugin" of the workspace template (templates/org-miniapp, coder_app.plugin).
const DEV_APP_SLUG = "plugin";
// The port URL host, DEV_ALLOWED_HOSTS and the host of the "Plugin" button (plugin--<workspace>--<owner>--<org>...).
const ALLOWED_HOSTS = [
  ...devAllowedHosts(DEV_PORT),
  ...appButtonHosts(DEV_PORT, DEV_APP_SLUG),
];
// The demo API (../api/configs/config.toml, server.port).
const BACKEND_ORIGIN = "http://127.0.0.1:21514";
// The organisation's DEV backend (the Hub), as reached from a Coder workspace.
const DEV_HUB_ORIGIN =
  process.env.DEV_HUB_ORIGIN ?? "http://backend-service:8080";

export default defineConfig({
  // Same rule as ../miniapp/vite.config.ts: a 403 for any Host that is not the Coder port URL of 21516 (read from
  // VSCODE_PROXY_URI), DEV_ALLOWED_HOSTS (comma separated) or a loopback name. IP addresses included.
  plugins: [react(), tailwindcss(), hostGuard(ALLOWED_HOSTS)],
  resolve: {
    alias: { "@plugin": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  server: {
    allowedHosts: ALLOWED_HOSTS,
    // 0.0.0.0 so Coder lists the port in "Open ports".
    host: true,
    port: DEV_PORT,
    // Same origin as the page: no CORS.
    proxy: {
      "/api/": BACKEND_ORIGIN,
      "/hub/": {
        changeOrigin: true,
        rewrite: (url) => url.replace(/^\/hub/, ""),
        target: DEV_HUB_ORIGIN,
      },
    },
    strictPort: true,
  },
});
