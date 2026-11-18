import { devUserAtom } from "@app/atoms/devSession";
import { getErrorMessage } from "@app/lib/errors";
import { useAtom } from "jotai";
import { useCallback, useEffect, useState } from "react";
import { saveUser, scopedTokenFor, type TestUser } from "./devHub";

// A scoped token lives 5 minutes: fetch a new one a minute before.
const REFRESH_MS = 4 * 60 * 1000;

export interface DevSession {
  user: TestUser | null;
  token: string;
  error: string;
  signIn: (user: TestUser | null) => void;
}

// Development only: the scoped token of the picked test user, kept fresh.
// `enabled` false (production build, or VITE_DEV_TOKEN set) does nothing.
export function useDevSession(enabled: boolean): DevSession {
  const [user, setUser] = useAtom(devUserAtom);
  const [token, setToken] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    setToken("");
    setError("");
    if (!enabled || !user) return;
    let cancelled = false;
    const refresh = async () => {
      try {
        const next = await scopedTokenFor(user);
        if (!cancelled) {
          setToken(next);
          setError("");
        }
      } catch (cause) {
        if (!cancelled) setError(getErrorMessage(cause));
      }
    };
    void refresh();
    const timer = window.setInterval(() => void refresh(), REFRESH_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [enabled, user]);

  const signIn = useCallback(
    (next: TestUser | null) => {
      saveUser(next);
      setUser(next);
    },
    [setUser],
  );

  return { error, signIn, token, user };
}
