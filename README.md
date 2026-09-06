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

## Local development ($0)

No paid infrastructure, no live provider credentials, and no full MusicBrainz dump
download required to work on this project locally. See `docs/architecture.md` section D
for why development and production infrastructure are deliberately different.

```bash
# 1. Start Postgres (pgvector/pgvector:pg16 — Postgres 16 + pgvector, pg_trgm/pgcrypto
#    come bundled with any Postgres image)
docker compose up -d

# 2. Apply every migration in database/migrations/, in order
./database/apply_migrations.sh

# 3. Seed a small, hand-authored, MusicBrainz-shaped dataset (NOT a verified live
#    extract, NOT a filtered "popular songs" production catalog — see the module
#    docstring) through the real ingestion pipeline
pip install -e packages/provider-types -e packages/contracts -e apps/api[dev]
python -m jobs.musicbrainz_ingest.dev_fixture

# 4. Run the backend
uvicorn app.main:app --app-dir apps/api --reload

# 5. Run the frontend (separate terminal)
cd apps/web && npm install && npm run dev
```

Run the test suite (unit tests need no database; integration tests need the Postgres
from step 1-2 above) with `pytest tests/ -q` from the repo root.

`.github/workflows/ci.yml` runs the same steps (a Postgres service container instead of
docker-compose, the same fixture, the same test suite) on every push.

## Status

Phase 1 (Platform MVP) in progress. No live provider credentials are required to build or
test this stage — provider adapters run against mocks until Phase 0 dashboard/licensing
verification is complete. See `docs/phase-0-checklist.md`. Production ingestion of the
full MusicBrainz catalog is deferred until the Phase 0 licensing items and the database
capacity benchmark (`docs/architecture.md` section G) are resolved — local development
does not wait on either.
