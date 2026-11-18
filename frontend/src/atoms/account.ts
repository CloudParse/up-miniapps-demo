import type { LoadState } from "@app/lib/loadState";
import type {
  IAchievement,
  IFidelityBalance,
  IUserProfile,
} from "@cloudparse/up-miniapps-sdk";
import { atom } from "jotai";

export const profileAtom = atom<LoadState<Partial<IUserProfile>>>({
  status: "idle",
});

export const balanceAtom = atom<LoadState<IFidelityBalance>>({
  status: "idle",
});

export const achievementsAtom = atom<LoadState<IAchievement[]>>({
  status: "idle",
});

// Achievements are displayed sequentially by priority: only the lowest-priority
// incomplete one is actionable, every later one stays locked until it completes.
// See the frontend convention "Achievement lists render sequentially, by priority".
export const orderedAchievementsAtom = atom((get) => {
  const state = get(achievementsAtom);
  if (state.status !== "ready") return [];
  return [...state.data].sort((a, b) => a.priority - b.priority);
});

export const currentAchievementPriorityAtom = atom((get) =>
  get(orderedAchievementsAtom)
    .filter((achievement) => !achievement.completed)
    .reduce(
      (min, achievement) => Math.min(min, achievement.priority),
      Number.POSITIVE_INFINITY,
    ),
);

export const avatarAtom = atom<LoadState<string>>({ status: "idle" });
