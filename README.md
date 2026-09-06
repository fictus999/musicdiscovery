# Music Discovery Platform

A music discovery product built around an independent, provider-agnostic recommendation
engine. Spotify and Apple Music are listening/catalog *integrations*, never the source of
truth for search or recommendation data.

See `docs/architecture.md` for the full architecture rationale and `docs/phase-0-checklist.md`
for the feasibility gate that must clear before production reliance on any provider or
external dataset.

## Repository structure

```
apps/
  web/            Next.js + TypeScript frontend
  api/             FastAPI + Python backend
packages/
  contracts/       Shared API request/response schemas
  provider-types/  CatalogProvider / MusicProvider / ArtworkProvider interfaces
database/
  migrations/      SQL migrations (canonical catalog + app schema)
ml/
  datasets/        Metadata only — never commit raw dumps or model weights
  feature_pipelines/
  embeddings/
  evaluation/
jobs/              Background/batch jobs (MusicBrainz ingestion, refresh, embeddings)
tests/
docs/
```

## Status

Phase 1 (Platform MVP) in progress. No live provider credentials are required to build or
test this stage — provider adapters run against mocks until Phase 0 dashboard/licensing
verification is complete. See `docs/phase-0-checklist.md`.
