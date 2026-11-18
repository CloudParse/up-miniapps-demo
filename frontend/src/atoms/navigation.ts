import type { TabId } from "@app/config/tabs";
import { atom } from "jotai";

export type ToolsPage =
  | "index"
  | "network"
  | "realtime"
  | "haptics"
  | "permissions"
  | "storage"
  | "ui-kit"
  | "system";

export type Overlay =
  | { kind: "none" }
  | { kind: "exit" }
  | { kind: "poi"; poiId: string }
  | { kind: "demo-confirm" };

export const activeTabAtom = atom<TabId>("home");
export const toolsPageAtom = atom<ToolsPage>("index");
export const overlayAtom = atom<Overlay>({ kind: "none" });
