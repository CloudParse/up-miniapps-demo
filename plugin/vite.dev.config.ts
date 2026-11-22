import { fileURLToPath } from "node:url";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Development only (`npm run dev`): a small page, index.html, that runs the plugin outside
// the Studio. It is NOT the production build (vite.config.ts): React is bundled here,
// the Studio supplies its own.
const DEV_PORT = 21516;
// The demo API (../api/configs/config.toml, server.port).
const BACKEND_ORIGIN = "http://127.0.0.1:21514";
// The organisation's DEV backend (the Hub), as reached from a Coder workspace.
const DEV_HUB_ORIGIN =
  process.env.DEV_HUB_ORIGIN ?? "http://backend-service:8080";

// Same rule as ../miniapp/vite.config.ts: Vite answers only to the hosts it knows. In a
// Coder workspace, VSCODE_PROXY_URI is the port URL template
// (https://{{port}}--<agent>--<workspace>--<owner>--<org>.<apps domain>): allow exactly
// the host of this port. DEV_ALLOWED_HOSTS (comma separated) adds hosts by hand.
function devAllowedHosts(): string[] {
  const hosts = (process.env.DEV_ALLOWED_HOSTS ?? "")
    .split(",")
    .map((host) => host.trim())
    .filter((host) => host.length > 0);
  const coderProxy = process.env.VSCODE_PROXY_URI;
  if (coderProxy) {
    hosts.push(
      new URL(coderProxy.replace("{{port}}", String(DEV_PORT))).hostname,
    );
  }
  return hosts;
}

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@plugin": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  server: {
    allowedHosts: devAllowedHosts(),
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
