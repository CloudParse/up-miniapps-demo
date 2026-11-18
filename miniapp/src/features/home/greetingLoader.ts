import { greetingAtom } from "@app/atoms/greeting";
import { getErrorMessage } from "@app/lib/errors";
import { appStore } from "@app/lib/store";
import { fetchGreeting } from "@app/services/helloService";

// Runs once per session, like the account loaders. Only a pull-to-refresh forces a reload.
export async function loadGreeting(force = false): Promise<void> {
  if (!force && appStore.get(greetingAtom).status === "ready") return;
  appStore.set(greetingAtom, { status: "loading" });
  try {
    appStore.set(greetingAtom, {
      data: await fetchGreeting(),
      status: "ready",
    });
  } catch (error) {
    appStore.set(greetingAtom, {
      message: getErrorMessage(error),
      status: "error",
    });
  }
}
