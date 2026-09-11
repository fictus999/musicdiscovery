"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getSavedSongs, type SongDTO } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function SavedSongsPage() {
  const { loading: authLoading } = useAuth();
  const [songs, setSongs] = useState<SongDTO[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Wait for AuthProvider's effect to populate currentAuth (dev user id or
    // Supabase session) — it's the parent, so its effect runs after this
    // one on mount, and firing this fetch first would send an unauthenticated
    // request that 401s.
    if (authLoading) return;
    setError(null);
    getSavedSongs()
      .then((response) => setSongs(response.songs))
      .catch(() => setError("Could not load saved songs."));
  }, [authLoading]);

  return (
    <main className="container">
      <section className="hero">
        <h1>Saved songs</h1>
      </section>

      {error && <p className="empty-state">{error}</p>}
      {songs === null && !error && <p className="empty-state">Loading…</p>}

      {songs !== null && (
        <ul className="song-list">
          {songs.length === 0 && <li className="empty-state">Nothing saved yet.</li>}
          {songs.map((song) => (
            <li key={song.recording_id} className="song-row">
              <div>
                <div className="song-title">{song.title}</div>
                <div className="song-artist">{song.artist_names.join(", ")}</div>
              </div>
              <Link className="link-btn" href={`/song/${song.recording_id}`}>
                View
              </Link>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
