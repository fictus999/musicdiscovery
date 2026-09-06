-- App-side identity and entitlements. app_users.id mirrors the Supabase Auth
-- user id (auth.users) rather than duplicating authentication — this table
-- holds product-specific profile/entitlement state only.

create table if not exists app_users (
    id            uuid primary key,   -- = auth.users.id
    email         text,
    display_name  text,
    created_at    timestamptz not null default now(),
    updated_at    timestamptz not null default now()
);

create table if not exists subscriptions (
    id                     uuid primary key default gen_random_uuid(),
    user_id                uuid not null references app_users(id) on delete cascade,
    plan                   text not null default 'free' check (plan in ('free', 'pro')),
    status                 text not null default 'active'
                               check (status in ('active', 'past_due', 'canceled', 'trialing')),
    payment_provider       text check (payment_provider in ('stripe', 'razorpay')),
    external_subscription_id text,
    current_period_end    timestamptz,
    created_at             timestamptz not null default now(),
    updated_at             timestamptz not null default now(),
    unique (user_id)
);

-- A user may exist without ever connecting a provider (V2.2 §5). Tokens are
-- only present for USER_OAUTH connections; Client Credentials access never
-- creates a row here because it isn't tied to any one user.
create table if not exists user_provider_connections (
    id                    uuid primary key default gen_random_uuid(),
    user_id               uuid not null references app_users(id) on delete cascade,
    provider              text not null references catalog_sources(id),
    provider_user_id      text,
    access_token_encrypted    bytea,
    refresh_token_encrypted   bytea,
    scopes                text[],
    connected_at          timestamptz not null default now(),
    expires_at            timestamptz,
    refresh_expires_at    timestamptz,  -- Spotify refresh tokens: 6-month lifetime (2026-06-18 policy)
    disconnected_at       timestamptz,
    unique (user_id, provider)
);

create table if not exists api_usage (
    id          uuid primary key default gen_random_uuid(),
    user_id     uuid references app_users(id) on delete set null,
    endpoint    text not null,
    usage_date  date not null default current_date,
    request_count integer not null default 0,
    unique (user_id, endpoint, usage_date)
);
