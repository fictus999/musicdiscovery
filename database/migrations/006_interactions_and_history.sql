set search_path = app, music_catalog, public;

-- Saved songs, search history, and interaction events. user_id is nullable
-- throughout: search and recommendations work for anonymous/unauthenticated
-- product usage (V2.2 §5 — no provider or app login required to discover).

create table if not exists saved_songs (
    id           uuid primary key default gen_random_uuid(),
    user_id      uuid not null references app_users(id) on delete cascade,
    recording_id uuid not null references recording(id) on delete cascade,
    saved_at     timestamptz not null default now(),
    unique (user_id, recording_id)
);

create table if not exists search_history (
    id          uuid primary key default gen_random_uuid(),
    user_id     uuid references app_users(id) on delete cascade,
    session_id  text,        -- for anonymous users, a client-generated id
    query_text  text not null,
    created_at  timestamptz not null default now()
);
create index if not exists idx_search_history_user on search_history (user_id, created_at desc);

create table if not exists user_interactions (
    id            uuid primary key default gen_random_uuid(),
    user_id       uuid references app_users(id) on delete cascade,
    session_id    text,
    recording_id  uuid references recording(id) on delete cascade,
    interaction_type text not null
                      check (interaction_type in
                          ('click', 'open', 'save', 'unsave', 'hide', 'like', 'dislike', 'search', 'repeat')),
    metadata      jsonb not null default '{}'::jsonb,
    created_at    timestamptz not null default now()
);
create index if not exists idx_user_interactions_user on user_interactions (user_id, created_at desc);
create index if not exists idx_user_interactions_recording on user_interactions (recording_id);
