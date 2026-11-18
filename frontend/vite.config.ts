import path from "node:path";
import { fileURLToPath } from "node:url";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { viteSingleFile } from "vite-plugin-singlefile";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

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
    host: true,
    port: 21515,
    strictPort: true,
  },
});
