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
// `enabled` false does nothing.
export function useDevSession(enabled: boolean): DevSession {
  const [user, setUser] = useAtom(devUserAtom);
  const [token, setToken] = useState("");
  const [error, setError] = useState("");
  // bumped on every pick: picking the same user again after a failure retries the sign-in
  const [attempt, setAttempt] = useState(0);

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
  }, [enabled, user, attempt]);

  const signIn = useCallback(
    (next: TestUser | null) => {
      saveUser(next);
      setUser(next);
      setAttempt((n) => n + 1);
    },
    [setUser],
  );

  return { error, signIn, token, user };
}
