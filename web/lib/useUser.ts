"use client";

import { useEffect, useState } from "react";

// MVP identity: a localStorage-persisted user id (email). No auth yet (roadmap P3 #13) — this is the
// key the backend persists progress under, nothing more.
const KEY = "mindmorph.userId";

export function useUser() {
  const [userId, setUserId] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setUserId(localStorage.getItem(KEY));
    setReady(true);
  }, []);

  const signIn = (id: string) => {
    const v = id.trim();
    if (!v) return;
    localStorage.setItem(KEY, v);
    setUserId(v);
  };

  const signOut = () => {
    localStorage.removeItem(KEY);
    setUserId(null);
  };

  return { userId, ready, signIn, signOut };
}
