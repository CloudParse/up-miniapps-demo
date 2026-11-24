import { definePlugin } from "@cloudparse/up-backoffice-sdk";
import { DemoPage } from "@plugin/features/demo/DemoPage";
import { NotesPage } from "@plugin/features/demo/NotesPage";
import { LayoutDashboard, StickyNote } from "lucide-react";
import styles from "./styles.css?inline";

// The default export is the whole plugin: the Studio loads it and renders its pages.
// Keep the id lowercase (letters, digits, dashes). Rename it for your mini-app: two mini-apps
// copied from the template would otherwise publish the same id.
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
    {
      component: NotesPage,
      description: "Admins write notes into the mini-app's database.",
      icon: StickyNote,
      path: "notes",
      title: "Notes",
    },
  ],
  styles,
});
