"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth";

export function NavBar() {
  const { loading, devMode, displayId, signOut } = useAuth();

  return (
    <div className="top-nav">
      <div className="container nav-row">
        <Link href="/" className="brand">
          Music Discovery
        </Link>
        <nav className="nav-links">
          <Link href="/saved">Saved</Link>
          <Link href="/history">History</Link>
          {!loading && devMode && <span className="pill">dev mode: {displayId}</span>}
          {!loading && !devMode && displayId && (
            <>
              <span className="nav-user">{displayId}</span>
              <button className="link-btn" onClick={() => signOut()}>
                Sign out
              </button>
            </>
          )}
          {!loading && !devMode && !displayId && <Link href="/sign-in">Sign in</Link>}
        </nav>
      </div>
    </div>
  );
}
