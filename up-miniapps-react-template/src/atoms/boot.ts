import { atom } from "jotai";

export type BootState =
  | { phase: "loading" }
  | { phase: "ready" }
  | { phase: "error"; message: string };

export const bootAtom = atom<BootState>({ phase: "loading" });
