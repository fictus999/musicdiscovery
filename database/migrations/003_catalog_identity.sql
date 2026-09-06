-- External identifiers (ISRC first-class among them) and a registry of
-- which catalog/data sources the system is permitted to draw from, with
-- enough metadata to answer "is this still a Phase-0-approved source"
-- without grepping through spec documents.

create table if not exists recording_external_ids (
    id            uuid primary key default gen_random_uuid(),
    recording_id  uuid not null references recording(id) on delete cascade,
    id_type       text not null,          -- 'isrc', 'discogs', 'acoustid', ...
    value         text not null,
    verified      boolean not null default false,
    created_at    timestamptz not null default now(),
    unique (id_type, value)
);
create index if not exists idx_recording_external_ids_recording
    on recording_external_ids (recording_id);
create index if not exists idx_recording_external_ids_isrc
    on recording_external_ids (value) where id_type = 'isrc';

create table if not exists catalog_sources (
    id                  text primary key,   -- 'musicbrainz', 'spotify', 'apple_music', 'cover_art_archive'
    display_name        text not null,
    license_summary     text,
    commercial_use_ok   boolean not null default false,
    phase0_approved      boolean not null default false,
    phase0_approved_at   timestamptz,
    notes               text,
    updated_at          timestamptz not null default now()
);

insert into catalog_sources (id, display_name, commercial_use_ok, phase0_approved, notes)
values
    ('musicbrainz', 'MusicBrainz', false, false,
     'License/commercial-use terms pending Phase 0 verification (see docs/phase-0-checklist.md).'),
    ('spotify', 'Spotify', false, false,
     'Client Credentials catalog lookups only; never a training-data source. Endpoints pending Phase 0 verification.'),
    ('apple_music', 'Apple Music', false, false,
     'MusicKit entitlement/catalog capabilities pending Phase 0 verification.'),
    ('cover_art_archive', 'Cover Art Archive', false, false,
     'Coverage and license pending Phase 0 artwork audit.')
on conflict (id) do nothing;
