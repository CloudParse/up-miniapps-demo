import path from "node:path";
import { fileURLToPath } from "node:url";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { viteSingleFile } from "vite-plugin-singlefile";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// The production build is ONE self-contained dist/index.html: `up-sdk build`
// injects it straight into the native WebView, there is no HTTP server to
// fetch separate chunks or assets from.
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
  plugins: [react(), tailwindcss(), viteSingleFile()],
  resolve: {
    alias: {
      "@app": path.resolve(__dirname, "./src"),
    },
    // Two copies of React (ours + the SDK's) break hooks at runtime.
    dedupe: ["react", "react-dom", "jotai"],
  },
  server: {
    host: true,
    port: 21515,
    strictPort: true,
  },
});
