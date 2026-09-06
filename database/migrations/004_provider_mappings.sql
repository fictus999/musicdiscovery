set search_path = music_catalog, public;

-- Provider identifiers are mappings onto the canonical recording, never the
-- primary key for a song. A row can exist with status='unresolved' and a
-- null provider_track_id — that's how "we tried to resolve this recording
-- against Spotify and it failed" is represented without losing the
-- canonical song (see V2.2 degradation rules).

create table if not exists provider_track_mappings (
    id                     uuid primary key default gen_random_uuid(),
    recording_id           uuid not null references recording(id) on delete cascade,
    provider               text not null references catalog_sources(id),
    provider_track_id      text,
    provider_url           text,
    match_method           text,        -- 'isrc', 'title_artist_duration', 'manual'
    match_confidence       numeric(4,3),
    status                 text not null default 'unresolved'
                               check (status in ('unresolved', 'resolved', 'stale', 'failed')),
    last_verified_at       timestamptz,
    provider_metadata_version text,
    created_at             timestamptz not null default now(),
    updated_at             timestamptz not null default now(),
    unique (recording_id, provider)
);
create index if not exists idx_provider_track_mappings_recording
    on provider_track_mappings (recording_id);

-- Artwork is its own concern (ArtworkProvider), keyed at the release level
-- because that's what Cover Art Archive indexes by; a recording resolves
-- artwork through whichever release it appears on.
create table if not exists artwork (
    id            uuid primary key default gen_random_uuid(),
    release_id    uuid references release(id) on delete cascade,
    recording_id  uuid references recording(id) on delete cascade,
    source        text not null references catalog_sources(id),
    image_url     text not null,
    width         integer,
    height        integer,
    is_fallback   boolean not null default false,
    fetched_at    timestamptz not null default now(),
    check (release_id is not null or recording_id is not null)
);
create index if not exists idx_artwork_release on artwork (release_id);
create index if not exists idx_artwork_recording on artwork (recording_id);

-- Normalized-query cache for catalog search. Debounced client-side; this
-- table is the server-side layer so repeated/common queries don't re-hit
-- Postgres FTS+trigram scoring (and never the MusicBrainz live API).
create table if not exists catalog_search_cache (
    normalized_query  text primary key,
    results           jsonb not null,
    source            text not null references catalog_sources(id),
    created_at        timestamptz not null default now(),
    expires_at        timestamptz not null
);
create index if not exists idx_catalog_search_cache_expires on catalog_search_cache (expires_at);
