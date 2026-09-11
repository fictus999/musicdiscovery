"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { getRecommendations, saveSong, unsaveSong, type RecommendationResponse } from "@/lib/api";

export default function SongDetailPage() {
  // Route params arrive as a Promise on the `params` prop in this Next.js
  // version (App Router) — useParams() is the client-component-safe way
  // to read them without an `await`/`use()` unwrap dance.
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<RecommendationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    getRecommendations(id)
      .then((response) => {
        if (!cancelled) setData(response);
      })
      .catch(() => {
        if (!cancelled) setError("Recommendations are unavailable right now.");
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  async function toggleSave() {
    if (!id) return;
    setSaveError(null);
    try {
      if (saved) {
        await unsaveSong(id);
        setSaved(false);
      } else {
        await saveSong(id);
        setSaved(true);
      }
    } catch {
      setSaveError("Could not update saved songs right now.");
    }
  }

  if (error) {
    return (
      <main className="container">
        <p className="empty-state">{error}</p>
      </main>
    );
  }

  if (!data) {
    return (
      <main className="container">
        <p className="empty-state">Loading…</p>
      </main>
    );
  }

  return (
    <main className="container">
      <section className="hero">
        <div className="song-detail-header">
          <div>
            <h1>{data.reference.title}</h1>
            <p>{data.reference.artist_names.join(", ")}</p>
          </div>
          <button className="btn" onClick={toggleSave}>
            {saved ? "Saved" : "Save"}
          </button>
        </div>
        {saveError && <p className="empty-state">{saveError}</p>}
      </section>

      <ul className="song-list">
        {data.results.length === 0 && (
          <li className="empty-state">
            No similar songs found yet — this Phase 1 seed catalog is small, and ranking is
            metadata-only (see model_version: {data.model_version}).
          </li>
        )}
        {data.results.map((result) => (
          <li key={result.song.recording_id} className="song-row">
            <div>
              <div className="song-title">{result.song.title}</div>
              <div className="song-artist">{result.song.artist_names.join(", ")}</div>
              <div className="reason-codes">
                {result.reason_codes.map((code) => (
                  <span key={code} className="pill">
                    {code.replaceAll("_", " ").toLowerCase()}
                  </span>
                ))}
              </div>
            </div>
            <div className="score">{result.score.toFixed(2)}</div>
          </li>
        ))}
      </ul>
    </main>
  );
}
