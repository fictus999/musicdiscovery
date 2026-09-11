import { currentAuth } from "./auth";

export interface ProviderLink {
  provider: string;
  status: string;
  url: string | null;
}

export interface SongDTO {
  recording_id: string;
  title: string;
  artist_names: string[];
  album_title: string | null;
  length_ms: number | null;
  artwork_url: string | null;
  provider_links: ProviderLink[];
}

export interface SearchResponse {
  query: string;
  results: SongDTO[];
}

export interface RecommendationResult {
  song: SongDTO;
  score: number;
  dimension_scores: Record<string, number>;
  reason_codes: string[];
}

export interface RecommendationResponse {
  reference: SongDTO;
  mode: string;
  results: RecommendationResult[];
  model_version: string;
}

export interface SavedSongsResponse {
  songs: SongDTO[];
}

export interface HistoryEntry {
  query_text: string;
  created_at: string;
}

export interface HistoryResponse {
  entries: HistoryEntry[];
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

// Real Supabase session -> Authorization: Bearer <jwt> (verified server-side
// via JWKS, see apps/api/app/auth.py). No Supabase project configured ->
// X-User-Id with a locally-generated dev id (server-side AUTH_DEV_MODE must
// also be on, or these calls 401 — that's intentional, not a bug: dev mode
// is an explicit opt-in on both sides, never a silent default in production).
function authHeaders(): Record<string, string> {
  if (currentAuth.accessToken) {
    return { Authorization: `Bearer ${currentAuth.accessToken}` };
  }
  if (currentAuth.devUserId) {
    return { "X-User-Id": currentAuth.devUserId };
  }
  return {};
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...authHeaders(), ...init?.headers },
  });
  if (!response.ok) {
    throw new Error(`${init?.method ?? "GET"} ${path} failed: ${response.status}`);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export function searchSongs(query: string): Promise<SearchResponse> {
  const params = new URLSearchParams({ q: query });
  return apiFetch<SearchResponse>(`/music/search?${params.toString()}`);
}

export function getRecommendations(
  trackId: string,
  options: { mode?: string; limit?: number } = {},
): Promise<RecommendationResponse> {
  return apiFetch<RecommendationResponse>("/recommendations", {
    method: "POST",
    body: JSON.stringify({
      track_id: trackId,
      mode: options.mode ?? "overall",
      limit: options.limit ?? 20,
    }),
  });
}

export function saveSong(recordingId: string): Promise<{ status: string }> {
  return apiFetch(`/songs/${recordingId}/save`, { method: "POST" });
}

export function unsaveSong(recordingId: string): Promise<{ status: string }> {
  return apiFetch(`/songs/${recordingId}/save`, { method: "DELETE" });
}

export function getSavedSongs(): Promise<SavedSongsResponse> {
  return apiFetch<SavedSongsResponse>("/me/saved-songs");
}

export function getHistory(): Promise<HistoryResponse> {
  return apiFetch<HistoryResponse>("/me/history");
}
