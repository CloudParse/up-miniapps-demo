// Memory of the workspace, for the console. A Coder workspace is capped at 4 GiB (template org-miniapp, story 055.8): when it is full the
// sandbox kills processes, and a Vite server (about 350 MB) is the usual victim. The console shows the figure and refuses to start a part
// when too little is free, with a message, instead of letting the sandbox decide.
import { readFileSync } from "node:fs";

export interface MemoryInfo {
  totalMiB: number;
  usedMiB: number;
  availableMiB: number;
}

/** Parses /proc/meminfo text. `used` is total minus available (file cache that can be dropped is available). */
export function parseMeminfo(text: string): MemoryInfo | null {
  const kib = (key: string): number | null => {
    const m = new RegExp(`^${key}:\\s+(\\d+)\\s+kB`, "m").exec(text);
    return m ? Number(m[1]) : null;
  };
  const total = kib("MemTotal");
  const available = kib("MemAvailable");
  if (total === null || available === null) return null;
  return { totalMiB: Math.round(total / 1024), availableMiB: Math.round(available / 1024), usedMiB: Math.round((total - available) / 1024) };
}

export function readMemory(path = "/proc/meminfo"): MemoryInfo | null {
  try {
    return parseMeminfo(readFileSync(path, "utf8"));
  } catch {
    return null; // not Linux: no figure, no guard
  }
}

/** The part needs about this much to start (a Vite server, the API with its reload worker). */
export const START_NEEDS_MIB = 200;

/** A message when starting a part now would likely fill the memory, else null. */
export function startRefusal(memory: MemoryInfo | null, needMiB = START_NEEDS_MIB): string | null {
  if (!memory) return null;
  if (memory.availableMiB >= needMiB) return null;
  return `pas assez de mémoire : ${memory.availableMiB} Mio libres sur ${memory.totalMiB} Mio. Arrête une autre partie (ou ferme des onglets de VS Code) puis recommence.`;
}
