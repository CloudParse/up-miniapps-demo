import "@cloudparse/up-miniapps-sdk/style.css";
import "@app/styles/index.css";
import App from "@app/App";
import maplibreWorkerSource from "@app/assets/maplibre-gl-worker.bundled.js?raw";
import { setWorkerUrl } from "maplibre-gl";
import { createRoot } from "react-dom/client";

// maplibre-gl resolves its worker via import.meta.url, which a single-file
// WebView build cannot serve. The worker is inlined and handed over as a Blob.
setWorkerUrl(
  URL.createObjectURL(
    new Blob([maplibreWorkerSource], { type: "text/javascript" }),
  ),
);

const container = document.getElementById("root");

if (!container) {
  throw new Error("Root element not found");
}

createRoot(container).render(<App />);
