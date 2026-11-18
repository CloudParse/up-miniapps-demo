import type { LoadState } from "@app/lib/loadState";
import type { Greeting } from "@app/services/helloService";
import { atom } from "jotai";

export const greetingAtom = atom<LoadState<Greeting>>({ status: "idle" });
