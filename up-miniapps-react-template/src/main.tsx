import "@cloudparse/up-miniapps-sdk/style.css";
import "@app/styles/index.css";
import App from "@app/App";
import { createRoot } from "react-dom/client";

const container = document.getElementById("root");

if (!container) {
  throw new Error("Root element not found");
}

createRoot(container).render(<App />);
