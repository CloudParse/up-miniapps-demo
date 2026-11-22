import { fileURLToPath } from "node:url";
import { backofficePlugin } from "@cloudparse/up-backoffice-sdk/vite";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Production build: `npm run build` writes dist/plugin.js, the one ES module that
// .gitea/workflows/deploy-plugin.yml publishes (miniapp.yaml, section `plugin`).
export default defineConfig({
  plugins: [react(), tailwindcss(), backofficePlugin()],
  resolve: {
    alias: { "@plugin": fileURLToPath(new URL("./src", import.meta.url)) },
  },
});
