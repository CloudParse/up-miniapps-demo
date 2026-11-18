import {
  achievementsAtom,
  avatarAtom,
  balanceAtom,
  profileAtom,
} from "@app/atoms/account";
import { getErrorMessage } from "@app/lib/errors";
import { appStore } from "@app/lib/store";
import { accountService } from "@app/services/accountService";
import { sdk } from "@cloudparse/up-miniapps-sdk";

// Each loader runs once per session. Revisiting a tab shows cached atoms and
// never refetches on its own. Only an explicit refresh (pull-to-refresh) does.

export async function loadProfile(force = false): Promise<void> {
  if (!force && appStore.get(profileAtom).status === "ready") return;
  appStore.set(profileAtom, { status: "loading" });
  try {
    const data = await accountService.getProfile();
    appStore.set(profileAtom, { data, status: "ready" });
  } catch (error) {
    appStore.set(profileAtom, {
      message: getErrorMessage(error),
      status: "error",
    });
  }
}

export async function loadBalance(force = false): Promise<void> {
  if (!force && appStore.get(balanceAtom).status === "ready") return;
  appStore.set(balanceAtom, { status: "loading" });
  try {
    const data = await accountService.getBalance();
    appStore.set(balanceAtom, { data, status: "ready" });
  } catch (error) {
    appStore.set(balanceAtom, {
      message: getErrorMessage(error),
      status: "error",
    });
  }
}

export async function loadAvatar(force = false): Promise<void> {
  if (!force && appStore.get(avatarAtom).status === "ready") return;
  appStore.set(avatarAtom, { status: "loading" });
  try {
    const data = await accountService.getPicture();
    appStore.set(avatarAtom, { data, status: "ready" });
  } catch (error) {
    appStore.set(avatarAtom, {
      message: getErrorMessage(error),
      status: "error",
    });
  }
}

export async function loadAchievements(force = false): Promise<void> {
  if (!force && appStore.get(achievementsAtom).status === "ready") return;
  appStore.set(achievementsAtom, { status: "loading" });
  try {
    const data = await sdk.achievements();
    appStore.set(achievementsAtom, { data, status: "ready" });
  } catch (error) {
    appStore.set(achievementsAtom, {
      message: getErrorMessage(error),
      status: "error",
    });
  }
}

export async function refreshAccount(): Promise<void> {
  await Promise.all([
    loadProfile(true),
    loadBalance(true),
    loadAvatar(true),
    loadAchievements(true),
  ]);
}
