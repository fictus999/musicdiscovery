"use client";

import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { createContext, useContext, useEffect, useState } from "react";

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

// No live Supabase project configured yet (Phase 0 — see docs/phase-0-checklist.md)
// falls back to a locally-generated dev user id, mirroring the backend's
// AUTH_DEV_MODE (apps/api/app/auth.py). Real sign-in only appears once
// both env vars are set; nothing here pretends dev mode is real auth.
export const isSupabaseConfigured = Boolean(SUPABASE_URL && SUPABASE_ANON_KEY);

let cachedClient: SupabaseClient | null = null;

function getSupabaseClient(): SupabaseClient {
  if (!cachedClient) {
    if (!isSupabaseConfigured) {
      throw new Error("Supabase is not configured (NEXT_PUBLIC_SUPABASE_URL / NEXT_PUBLIC_SUPABASE_ANON_KEY)");
    }
    cachedClient = createClient(SUPABASE_URL as string, SUPABASE_ANON_KEY as string);
  }
  return cachedClient;
}

const DEV_USER_ID_KEY = "musicdiscovery.devUserId";

function getOrCreateDevUserId(): string {
  let id = window.localStorage.getItem(DEV_USER_ID_KEY);
  if (!id) {
    id = crypto.randomUUID();
    window.localStorage.setItem(DEV_USER_ID_KEY, id);
  }
  return id;
}

// Read by lib/api.ts on every request — kept as a plain module-level object
// rather than routed through React context, since api.ts's fetch helpers
// aren't components and shouldn't need to be.
export const currentAuth: { accessToken: string | null; devUserId: string | null } = {
  accessToken: null,
  devUserId: null,
};

interface AuthState {
  loading: boolean;
  devMode: boolean;
  displayId: string | null; // dev user id or Supabase user id, for display only
  signInWithPassword: (email: string, password: string) => Promise<string | null>;
  signUpWithPassword: (email: string, password: string) => Promise<string | null>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [loading, setLoading] = useState(true);
  const [displayId, setDisplayId] = useState<string | null>(null);

  useEffect(() => {
    if (!isSupabaseConfigured) {
      const devId = getOrCreateDevUserId();
      currentAuth.devUserId = devId;
      setDisplayId(devId);
      setLoading(false);
      return;
    }

    const supabase = getSupabaseClient();
    supabase.auth.getSession().then(({ data }) => {
      currentAuth.accessToken = data.session?.access_token ?? null;
      setDisplayId(data.session?.user.email ?? data.session?.user.id ?? null);
      setLoading(false);
    });
    const { data: subscription } = supabase.auth.onAuthStateChange((_event, session) => {
      currentAuth.accessToken = session?.access_token ?? null;
      setDisplayId(session?.user.email ?? session?.user.id ?? null);
    });
    return () => subscription.subscription.unsubscribe();
  }, []);

  async function signInWithPassword(email: string, password: string) {
    const { error } = await getSupabaseClient().auth.signInWithPassword({ email, password });
    return error?.message ?? null;
  }

  async function signUpWithPassword(email: string, password: string) {
    const { error } = await getSupabaseClient().auth.signUp({ email, password });
    return error?.message ?? null;
  }

  async function signOut() {
    if (isSupabaseConfigured) {
      await getSupabaseClient().auth.signOut();
    }
  }

  return (
    <AuthContext.Provider
      value={{ loading, devMode: !isSupabaseConfigured, displayId, signInWithPassword, signUpWithPassword, signOut }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
