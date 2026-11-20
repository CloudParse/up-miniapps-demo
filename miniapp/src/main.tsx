import "@cloudparse/up-miniapps-sdk/style.css";
import "@app/styles/index.css";
import App from "@app/App";
import maplibreWorkerSource from "@app/assets/maplibre-gl-worker.bundled.js?raw";
import { setWorkerUrl } from "maplibre-gl";
import { createRoot } from "react-dom/client";

// maplibre-gl resolves its worker via import.meta.url, which a single-file
// WebView build cannot serve. The worker is inlined and handed over as a Blob.
// The bundled worker is a classic script (IIFE). maplibre-gl 6 starts a MODULE worker
// unless the URL ends with ".cjs", and a module worker from a Blob URL never loads in
// the opaque-origin frame of the UP platform (Web mini-apps). The "#.cjs" fragment is
// ignored when the Blob is read and makes maplibre-gl start a classic worker.
setWorkerUrl(
  `${URL.createObjectURL(
    new Blob([maplibreWorkerSource], { type: "text/javascript" }),
  )}#.cjs`,
);

const container = document.getElementById("root");

if (!container) {
  throw new Error("Root element not found");
}

createRoot(container).render(<App />);
