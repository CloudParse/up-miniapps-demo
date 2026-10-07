import type { IContextState } from "@cloudparse/up-miniapps-sdk";
import { atom } from "jotai";

// Everything the shell tells the mini-app (insets, env, ...), merged in place.
export const contextAtom = atom<IContextState>({
  insets: { bottom: 0, left: 0, right: 0, top: 0 },
});
