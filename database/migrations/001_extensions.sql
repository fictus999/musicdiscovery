-- Extensions required by the canonical catalog and recommendation engine.
-- pgvector is enabled now (Phase 2 populates song_embeddings) so the schema
-- doesn't need a breaking migration later; pg_trgm backs the Phase 1
-- Postgres-native search index over the ingested MusicBrainz catalog.
--
-- Extensions stay in `public` (their default). What's schema-separated is
-- the DATA: `music_catalog` holds the MusicBrainz-derived canonical
-- catalog, `app` holds everything application-specific (users, saved
-- songs, subscriptions, recommendation requests). One PostgreSQL
-- database/instance either way — see docs/architecture.md's "Schema
-- separation" note. Each subsequent migration file sets `search_path` at
-- its own top to land its tables in the right schema; application code
-- doesn't need schema-qualified table names because the runtime
-- connection sets the same search_path (see apps/api/app/db/session.py).

create schema if not exists music_catalog;
create schema if not exists app;

create extension if not exists pgcrypto;
create extension if not exists pg_trgm;
create extension if not exists vector;
