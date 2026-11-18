import { savedUser, type TestUser } from "@app/dev/devHub";
import { atom } from "jotai";

// Development only: the DEV backend test user the simulator signs in as
// (src/dev/DevUserPicker.tsx). Null until one is picked.
export const devUserAtom = atom<TestUser | null>(savedUser());
