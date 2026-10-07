import type { Greeting } from "@app/features/hello/types";
import { getErrorMessage } from "@app/lib/errors";
import { fetchGreeting } from "@app/services/helloService";
import { atom } from "jotai";

export type HelloState =
  | { phase: "loading" }
  | { phase: "ready"; greeting: Greeting }
  | { phase: "error"; message: string };

export const helloStateAtom = atom<HelloState>({ phase: "loading" });

// Write-only action atom: components trigger it, they never orchestrate the
// request themselves.
export const loadHelloAtom = atom(null, async (_get, set) => {
  set(helloStateAtom, { phase: "loading" });
  try {
    set(helloStateAtom, { greeting: await fetchGreeting(), phase: "ready" });
  } catch (error) {
    set(helloStateAtom, { message: getErrorMessage(error), phase: "error" });
  }
});
