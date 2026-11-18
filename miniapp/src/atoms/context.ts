import type { IContextState } from "@cloudparse/up-miniapps-sdk";
import { atom } from "jotai";

export const contextAtom = atom<IContextState>({
  insets: { bottom: 0, left: 0, right: 0, top: 0 },
});

export const isDarkAtom = atom((get) => {
  const value: unknown = get(contextAtom).isDark;
  return typeof value === "boolean" ? value : true;
});
