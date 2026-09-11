"use client";

import { useState } from "react";
import { useAuth, isSupabaseConfigured } from "@/lib/auth";

export default function SignInPage() {
  const { signInWithPassword, signUpWithPassword } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState<"sign-in" | "sign-up">("sign-in");
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  if (!isSupabaseConfigured) {
    return (
      <main className="container">
        <section className="hero">
          <h1>Sign in</h1>
          <p>
            No Supabase project is configured for this environment, so the app is running in local
            dev mode — every visitor already has a working (locally generated) identity. See
            docs/phase-0-checklist.md for what's still open before real sign-in is meaningful here.
          </p>
        </section>
      </main>
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setStatus(null);
    const action = mode === "sign-in" ? signInWithPassword : signUpWithPassword;
    const errorMessage = await action(email, password);
    if (errorMessage) {
      setError(errorMessage);
    } else if (mode === "sign-up") {
      setStatus("Check your email to confirm your account.");
    }
  }

  return (
    <main className="container">
      <section className="hero">
        <h1>{mode === "sign-in" ? "Sign in" : "Create an account"}</h1>
        <p>Connecting an account lets you save songs and see your search history.</p>

        <form className="search-form" onSubmit={handleSubmit} style={{ flexDirection: "column", alignItems: "stretch", gap: 12 }}>
          <input
            className="search-input"
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <input
            className="search-input"
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={6}
          />
          <button className="btn" type="submit">
            {mode === "sign-in" ? "Sign in" : "Sign up"}
          </button>
        </form>

        {error && <p className="empty-state">{error}</p>}
        {status && <p className="empty-state">{status}</p>}

        <div className="secondary-actions">
          <button className="link-btn" onClick={() => setMode(mode === "sign-in" ? "sign-up" : "sign-in")}>
            {mode === "sign-in" ? "Need an account? Sign up" : "Already have an account? Sign in"}
          </button>
        </div>
      </section>
    </main>
  );
}
