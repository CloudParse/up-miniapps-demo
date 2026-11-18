import path from "node:path";
import { fileURLToPath } from "node:url";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { viteSingleFile } from "vite-plugin-singlefile";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const DEV_PORT = 21515;
// The demo API (../api/configs/config.toml, server.port).
const BACKEND_ORIGIN = "http://127.0.0.1:21514";
// The organisation's DEV backend (the Hub), as reached from a Coder workspace. The
// test-user picker (src/dev/) signs in through /hub/. DEV_HUB_ORIGIN (a shell
// variable) points it elsewhere.
const DEV_HUB_ORIGIN = process.env.DEV_HUB_ORIGIN ?? "http://backend:8080";

// Vite answers only to the hosts it knows. In a Coder workspace, VSCODE_PROXY_URI
// is the port URL template (https://{{port}}--<agent>--<workspace>--<owner>--<org>.<apps domain>):
// allow exactly the host of this server's port, not the whole apps domain, which
// every organisation shares. DEV_ALLOWED_HOSTS (a shell variable, comma separated,
// a leading dot allows the subdomains) adds hosts by hand.
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

// Single self-contained dist/index.html, injected into the native WebView
// (see `up-sdk build`). maplibre-gl needs its worker inlined: see
// src/main.tsx's setWorkerUrl() call.
export default defineConfig({
  build: {
    assetsInlineLimit: 100000000,
    chunkSizeWarningLimit: 100000000,
    cssCodeSplit: false,
    modulePreload: false,
    rollupOptions: {
      output: {
        format: "iife",
        inlineDynamicImports: true,
      },
    },
    target: "es2015",
  },
  optimizeDeps: {
    // Vite's dev pre-bundler rewrites maplibre-gl's worker URL and the worker
    // then 404s in the dev server. Excluding it is Vite's documented fix.
    exclude: ["maplibre-gl"],
  },
  plugins: [react(), tailwindcss(), viteSingleFile()],
  resolve: {
    alias: {
      "@app": path.resolve(__dirname, "./src"),
    },
    // One copy of each: a second React (ours + the SDK's) breaks hooks at runtime.
    dedupe: [
      "react",
      "react-dom",
      "jotai",
      "maplibre-gl",
      "@vis.gl/react-maplibre",
    ],
  },
  server: {
    allowedHosts: devAllowedHosts(),
    // loopback only: Coder reaches the app at 127.0.0.1:21515, and nothing else in the cluster may (the dev server serves the
    // project's files)
    host: "127.0.0.1",
    port: DEV_PORT,
    // Same origin as the page: no CORS, and only port 21515 has to be opened.
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
