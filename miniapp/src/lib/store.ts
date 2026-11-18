import { getDefaultStore } from "jotai";

// The implicit default store, shared with React (no Provider in this app), so
// SDK event handlers and services can read and write atoms outside components.
export const appStore = getDefaultStore();
