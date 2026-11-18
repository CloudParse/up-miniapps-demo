import { atom } from "jotai";

export interface EventLogEntry {
  id: number;
  at: string;
  source: "shell" | "app";
  label: string;
}

const MAX_ENTRIES = 50;

export const eventLogAtom = atom<EventLogEntry[]>([]);

export const appendEventAtom = atom(
  null,
  (get, set, entry: Omit<EventLogEntry, "id" | "at">) => {
    const current = get(eventLogAtom);
    const next: EventLogEntry = {
      at: new Date().toLocaleTimeString("fr-FR"),
      id: (current[0]?.id ?? 0) + 1,
      ...entry,
    };
    set(eventLogAtom, [next, ...current].slice(0, MAX_ENTRIES));
  },
);
