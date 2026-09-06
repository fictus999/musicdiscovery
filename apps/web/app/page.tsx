"use client";

import Link from "next/link";
import { useState } from "react";
import { searchSongs, type SongDTO } from "@/lib/api";

export default function HomePage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SongDTO[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const response = await searchSongs(query.trim());
      setResults(response.results);
    } catch {
      setError("Search is unavailable right now. Try again shortly.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="container">
      <section className="hero">
        <h1>Find music by what makes it feel the way it does.</h1>
        <p>Search a song. No account or provider connection required to discover.</p>

        <form className="search-form" onSubmit={handleSubmit}>
          <input
            className="search-input"
            type="text"
            placeholder="Search for a song or artist"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <button className="btn" type="submit" disabled={loading}>
            {loading ? "Searching…" : "Search"}
          </button>
        </form>

        <div className="secondary-actions">
          <span className="link-btn" title="Optional — connect later to import playlists and library">
            Connect Spotify (optional)
          </span>
          <span className="link-btn" title="Optional — connect later to import playlists and library">
            Connect Apple Music (optional)
          </span>
        </div>
      </section>

      {error && <p className="empty-state">{error}</p>}

      {results !== null && (
        <ul className="song-list">
          {results.length === 0 && <li className="empty-state">No songs matched that search.</li>}
          {results.map((song) => (
            <li key={song.recording_id} className="song-row">
              <div>
                <div className="song-title">{song.title}</div>
                <div className="song-artist">{song.artist_names.join(", ")}</div>
              </div>
              <Link className="link-btn" href={`/song/${song.recording_id}`}>
                Similar songs
              </Link>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
