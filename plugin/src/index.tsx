import { definePlugin } from "@cloudparse/up-backoffice-sdk";
import { DemoPage } from "@plugin/features/demo/DemoPage";
import { LayoutDashboard } from "lucide-react";
import styles from "./styles.css?inline";

// The default export is the whole plugin: the Studio loads it and renders its pages.
// Keep the id lowercase (letters, digits, dashes).
export default definePlugin({
  description: "Admin page of the demo mini-app.",
  icon: LayoutDashboard,
  id: "up-miniapps-demo",
  name: "Demo mini-app",
  pages: [
    {
      badge: "Demo",
      component: DemoPage,
      description: "What the demo API holds in its database, cache and bucket.",
      icon: LayoutDashboard,
      path: "",
      title: "Resources",
    },
  ],
  styles,
});
