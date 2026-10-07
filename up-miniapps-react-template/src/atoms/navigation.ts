import { atom } from "jotai";

export type Overlay = { kind: "none" } | { kind: "exit" };

export const overlayAtom = atom<Overlay>({ kind: "none" });
