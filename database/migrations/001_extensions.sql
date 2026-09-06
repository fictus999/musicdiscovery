-- Extensions required by the canonical catalog and recommendation engine.
-- pgvector is enabled now (Phase 2 populates song_embeddings) so the schema
-- doesn't need a breaking migration later; pg_trgm backs the Phase 1
-- Postgres-native search index over the ingested MusicBrainz catalog.

create extension if not exists pgcrypto;
create extension if not exists pg_trgm;
create extension if not exists vector;
