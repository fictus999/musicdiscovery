"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getHistory, type HistoryEntry } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function HistoryPage() {
  const { loading: authLoading } = useAuth();
  const [entries, setEntries] = useState<HistoryEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // See app/saved/page.tsx — must wait for AuthProvider's effect to
    // populate currentAuth before fetching, or this 401s on first mount.
    if (authLoading) return;
    setError(null);
    getHistory()
      .then((response) => setEntries(response.entries))
      .catch(() => setError("Could not load search history."));
  }, [authLoading]);

  return (
    <main className="container">
      <section className="hero">
        <h1>Search history</h1>
      </section>

      {error && <p className="empty-state">{error}</p>}
      {entries === null && !error && <p className="empty-state">Loading…</p>}

      {entries !== null && (
        <ul className="song-list">
          {entries.length === 0 && <li className="empty-state">No searches yet while signed in.</li>}
          {entries.map((entry, index) => (
            <li key={`${entry.query_text}-${entry.created_at}-${index}`} className="song-row">
              <div>
                <div className="song-title">{entry.query_text}</div>
                <div className="song-artist">{new Date(entry.created_at).toLocaleString()}</div>
              </div>
              <Link className="link-btn" href={`/?q=${encodeURIComponent(entry.query_text)}`}>
                Search again
              </Link>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
