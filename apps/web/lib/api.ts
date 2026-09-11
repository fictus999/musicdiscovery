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

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    throw new Error(`${init?.method ?? "GET"} ${path} failed: ${response.status}`);
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
