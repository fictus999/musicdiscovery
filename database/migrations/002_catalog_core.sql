-- Canonical catalog, modeled directly on MusicBrainz's own entity graph
-- (artist -> release_group -> release -> recording, plus work) so the
-- ingestion pipeline in jobs/musicbrainz_ingest maps 1:1 onto these tables
-- instead of forcing a lossy re-shape at import time.
--
-- mbid columns are nullable: not every canonical entity needs to originate
-- from MusicBrainz forever (a future catalog source, or a manually-entered
-- entity, is legitimate), but when present it must be unique so re-imports
-- and delta refreshes can upsert instead of duplicating.

create table if not exists artist (
    id              uuid primary key default gen_random_uuid(),
    mbid            uuid unique,
    name            text not null,
    sort_name       text,
    normalized_name text not null,
    disambiguation  text,
    country         text,
    artist_type     text,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now()
);
create index if not exists idx_artist_normalized_name_trgm
    on artist using gin (normalized_name gin_trgm_ops);

create table if not exists release_group (
    id                  uuid primary key default gen_random_uuid(),
    mbid                uuid unique,
    title               text not null,
    normalized_title    text not null,
    primary_type        text,
    first_release_date  date,
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now()
);

create table if not exists release (
    id               uuid primary key default gen_random_uuid(),
    mbid             uuid unique,
    release_group_id uuid references release_group(id) on delete set null,
    title            text not null,
    normalized_title text not null,
    release_date     date,
    country          text,
    status           text,
    barcode          text,
    created_at       timestamptz not null default now(),
    updated_at       timestamptz not null default now()
);
create index if not exists idx_release_release_group on release (release_group_id);

create table if not exists work (
    id               uuid primary key default gen_random_uuid(),
    mbid             uuid unique,
    title            text not null,
    normalized_title text not null,
    work_type        text,
    language          text,
    created_at       timestamptz not null default now(),
    updated_at       timestamptz not null default now()
);

-- `recording` is the audio-identity level: the entity ISRC attaches to, and
-- the level the recommendation engine and canonical_song_id (identity.py)
-- actually reason about. Title/duration are denormalized onto the row for
-- fast normalization/matching without a join.
create table if not exists recording (
    id                uuid primary key default gen_random_uuid(),
    mbid              uuid unique,
    title             text not null,
    normalized_title  text not null,
    length_ms         integer,
    language          text,
    identity_confidence numeric(4,3) not null default 1.0,
    created_at        timestamptz not null default now(),
    updated_at        timestamptz not null default now()
);
create index if not exists idx_recording_normalized_title_trgm
    on recording using gin (normalized_title gin_trgm_ops);

-- Many-to-many: a recording can credit multiple artists (features,
-- collaborations); an artist has many recordings.
create table if not exists recording_artists (
    recording_id uuid not null references recording(id) on delete cascade,
    artist_id    uuid not null references artist(id) on delete cascade,
    credit_order smallint not null default 0,
    join_phrase  text,
    primary key (recording_id, artist_id)
);

-- A recording performs a work (its abstract composition). This is what
-- lets "same song, different recording" (covers, live versions, remixes)
-- be related without conflating them as identical canonical entities.
create table if not exists recording_works (
    recording_id uuid not null references recording(id) on delete cascade,
    work_id      uuid not null references work(id) on delete cascade,
    primary key (recording_id, work_id)
);

-- Tracklist membership: which releases carry which recording, and where.
create table if not exists release_recordings (
    release_id      uuid not null references release(id) on delete cascade,
    recording_id    uuid not null references recording(id) on delete cascade,
    medium_number   smallint not null default 1,
    track_position  smallint not null,
    track_title     text,
    primary key (release_id, recording_id, medium_number, track_position)
);
create index if not exists idx_release_recordings_recording on release_recordings (recording_id);
