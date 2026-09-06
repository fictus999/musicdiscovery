-- Recommendation engine tables. Phase 1 only ever writes into song_features
-- with feature_family = 'metadata'; song_embeddings stays empty until
-- Phase 2 has an approved, permitted feature source (see
-- docs/phase-0-checklist.md — Phase 2 cannot begin until that's signed off).
--
-- Every feature/embedding/ranking row is versioned via model_versions so
-- evaluation results and cache keys stay reproducible (V2 §9.3, §24).

create table if not exists model_versions (
    id           uuid primary key default gen_random_uuid(),
    family       text not null check (family in ('feature', 'embedding', 'ranker')),
    version_tag  text not null,
    source       text references catalog_sources(id),
    description  text,
    created_at   timestamptz not null default now(),
    unique (family, version_tag)
);

create table if not exists song_features (
    id              uuid primary key default gen_random_uuid(),
    recording_id    uuid not null references recording(id) on delete cascade,
    feature_family  text not null,   -- 'metadata', 'audio', 'lyrics_theme', 'rhythm_cadence', ...
    model_version_id uuid not null references model_versions(id),
    payload         jsonb not null,
    created_at      timestamptz not null default now(),
    unique (recording_id, feature_family, model_version_id)
);

create table if not exists song_embeddings (
    id              uuid primary key default gen_random_uuid(),
    recording_id    uuid not null references recording(id) on delete cascade,
    embedding_type  text not null,  -- 'semantic', 'audio', 'lyrical', 'rhythm', 'metadata', 'artist'
    model_version_id uuid not null references model_versions(id),
    embedding       vector(384),
    created_at      timestamptz not null default now(),
    unique (recording_id, embedding_type, model_version_id)
);
-- ANN index intentionally deferred: created in a Phase 2 migration once a
-- real embedding_type/dimension is populated (ivfflat/hnsw need real data
-- distribution to tune `lists`/`m`, and an empty-table index is dead weight).

create table if not exists recommendations (
    id                  uuid primary key default gen_random_uuid(),
    requested_by_user_id uuid references app_users(id) on delete set null,
    reference_recording_id uuid not null references recording(id),
    mode                text not null,
    params              jsonb not null default '{}'::jsonb,
    model_version_id    uuid references model_versions(id),
    created_at          timestamptz not null default now()
);

create table if not exists recommendation_results (
    id                uuid primary key default gen_random_uuid(),
    recommendation_id uuid not null references recommendations(id) on delete cascade,
    recording_id      uuid not null references recording(id),
    rank              integer not null,
    score             numeric(6,5) not null,
    dimension_scores  jsonb not null default '{}'::jsonb,
    reason_codes      text[] not null default '{}',
    unique (recommendation_id, recording_id)
);
create index if not exists idx_recommendation_results_recommendation
    on recommendation_results (recommendation_id, rank);

create table if not exists evaluation_items (
    id                     uuid primary key default gen_random_uuid(),
    reference_recording_id uuid not null references recording(id),
    expected_recording_id  uuid not null references recording(id),
    dimension              text not null,
    human_rating           numeric(3,2),
    notes                  text,
    created_at              timestamptz not null default now()
);
