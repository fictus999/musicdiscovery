-- Canonical catalog, reconciled against MusicBrainz's real entity graph —
-- verified against `mbdata` (MetaBrainz's own SQLAlchemy schema mirror,
-- PyPI mbdata==31.0.1), not assumed from memory. See docs/architecture.md
-- section A for the full rationale, including the deliberate
-- simplifications (no area/country, no per-country release dates, no
-- genre/tag ingestion — MusicBrainz's tag tables are CC BY-NC-SA,
-- non-commercial, and are excluded from this schema entirely).
--
-- artist_credit / artist_credit_name is a reconciliation, not an
-- addition: MusicBrainz reuses one artist_credit row (e.g. "Daft Punk
-- feat. Pharrell Williams") across every recording/release/release_group
-- that shares that exact credit, preserving the credited display name
-- (which can differ from artist.name) and the join_phrase between
-- multiple artists. A flat recording<->artist join (the first schema
-- pass's `recording_artists`) can't represent either.
--
-- mbid columns are nullable: not every canonical entity needs to
-- originate from MusicBrainz forever, but when present it must be
-- unique so re-imports and delta refreshes upsert instead of
-- duplicating.

create table if not exists artist (
    id              uuid primary key default gen_random_uuid(),
    mbid            uuid unique,
    name            text not null,
    sort_name       text,
    normalized_name text not null,
    disambiguation  text,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now()
);
create index if not exists idx_artist_normalized_name_trgm
    on artist using gin (normalized_name gin_trgm_ops);

create table if not exists artist_credit (
    id         uuid primary key default gen_random_uuid(),
    mbid       uuid unique,
    name       text not null,  -- the rendered credit string, e.g. "Daft Punk feat. Pharrell Williams"
    created_at timestamptz not null default now()
);

create table if not exists artist_credit_name (
    artist_credit_id uuid not null references artist_credit(id) on delete cascade,
    position         smallint not null,
    artist_id        uuid not null references artist(id) on delete cascade,
    name             text not null default '',  -- credited name, may differ from artist.name
    join_phrase      text not null default '',
    primary key (artist_credit_id, position)
);
create index if not exists idx_artist_credit_name_artist on artist_credit_name (artist_id);

create table if not exists release_group (
    id                        uuid primary key default gen_random_uuid(),
    mbid                      uuid unique,
    artist_credit_id          uuid references artist_credit(id),
    title                     text not null,
    normalized_title          text not null,
    primary_type              text,
    -- Denormalized from MusicBrainz's release_group_meta: the earliest
    -- known release date for this group, independent of any specific
    -- edition/reissue. This is the "release period" signal ranking uses
    -- — modeling per-country release_country dates is deliberately out
    -- of scope (see docs/architecture.md).
    first_release_date_year  smallint,
    first_release_date_month smallint,
    first_release_date_day   smallint,
    created_at                timestamptz not null default now(),
    updated_at                timestamptz not null default now()
);
create index if not exists idx_release_group_normalized_title_trgm
    on release_group using gin (normalized_title gin_trgm_ops);

create table if not exists release (
    id               uuid primary key default gen_random_uuid(),
    mbid             uuid unique,
    release_group_id uuid references release_group(id) on delete set null,
    artist_credit_id uuid references artist_credit(id),
    title            text not null,
    normalized_title text not null,
    status           text,
    language         text,
    script           text,
    barcode          text,
    created_at       timestamptz not null default now(),
    updated_at       timestamptz not null default now()
);
create index if not exists idx_release_release_group on release (release_group_id);

create table if not exists medium (
    id          uuid primary key default gen_random_uuid(),
    mbid        uuid unique,
    release_id  uuid not null references release(id) on delete cascade,
    position    smallint not null,
    format      text,
    track_count integer not null default 0,
    created_at  timestamptz not null default now()
);
create index if not exists idx_medium_release on medium (release_id);

create table if not exists work (
    id               uuid primary key default gen_random_uuid(),
    mbid             uuid unique,
    title            text not null,
    normalized_title text not null,
    work_type        text,
    created_at       timestamptz not null default now(),
    updated_at       timestamptz not null default now()
);

create table if not exists work_languages (
    work_id  uuid not null references work(id) on delete cascade,
    language text not null,
    primary key (work_id, language)
);

-- `recording` is the audio-identity level: the entity ISRC attaches to,
-- and the level the recommendation engine and canonical identity
-- resolution (app/catalog/identity.py) actually reason about. Note
-- there is no `language` column here — MusicBrainz carries language on
-- `release`, not `recording`.
create table if not exists recording (
    id                   uuid primary key default gen_random_uuid(),
    mbid                 uuid unique,
    artist_credit_id     uuid references artist_credit(id),
    title                text not null,
    normalized_title     text not null,
    length_ms            integer,
    video                boolean not null default false,
    identity_confidence  numeric(4,3) not null default 1.0,
    created_at           timestamptz not null default now(),
    updated_at           timestamptz not null default now()
);
create index if not exists idx_recording_normalized_title_trgm
    on recording using gin (normalized_title gin_trgm_ops);
create index if not exists idx_recording_artist_credit on recording (artist_credit_id);

-- A track is a release's placement of a recording — distinct from the
-- recording itself because a track's title/length can differ from the
-- recording's own (e.g. a compilation retitles a track), matching
-- MusicBrainz's `track` table exactly.
create table if not exists track (
    id               uuid primary key default gen_random_uuid(),
    mbid             uuid unique,
    medium_id        uuid not null references medium(id) on delete cascade,
    recording_id     uuid not null references recording(id) on delete cascade,
    position         integer not null,
    number           text not null default '',
    title            text not null,
    artist_credit_id uuid references artist_credit(id),
    length_ms        integer,
    created_at       timestamptz not null default now()
);
create index if not exists idx_track_medium on track (medium_id, position);
create index if not exists idx_track_recording on track (recording_id);

-- A recording performs/derives-from a work (its abstract composition),
-- mirroring MusicBrainz's generic l_recording_work relationship. Not
-- filtered by MusicBrainz's link_type in Phase 1 (see docs/architecture.md)
-- — this materializes all such relationships undifferentiated.
create table if not exists recording_works (
    recording_id uuid not null references recording(id) on delete cascade,
    work_id      uuid not null references work(id) on delete cascade,
    primary key (recording_id, work_id)
);
