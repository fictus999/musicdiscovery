# MusicBrainz ingestion pipeline

Loads a MusicBrainz data dump into our own `artist` / `release_group` /
`release` / `recording` / `work` / `recording_external_ids` tables
(`database/migrations/002_catalog_core.sql`, `003_catalog_identity.sql`), so
Phase 1 search runs against our own indexed Postgres copy — never the live
MusicBrainz API per request (that API is rate-limited to roughly 1 req/sec
per IP, which is a bootstrapping/lookup tool, not a production search
backend for any real traffic volume).

## Pipeline stages (`pipeline.py`)

1. **download** (`download.py`) — fetch the dump archive, verify its
   checksum against MusicBrainz's published checksum file. Real, runnable
   logic — not stubbed.
2. **stage** (`staging.py`) — load raw dump rows into a `mb_staging` schema,
   1:1 with the dump's own structure, before any transformation. Keeping a
   staging copy means a bad transform run can be re-run without
   re-downloading.
3. **transform** (`transform.py`) — map staged rows onto our canonical
   schema (dedupe, normalize, populate `recording_external_ids` for ISRC).
4. **index** — the canonical tables' trigram/FTS indexes
   (`database/migrations/002_catalog_core.sql`) do this automatically;
   this stage runs `ANALYZE` after a bulk load so the planner has fresh
   statistics.
5. **validate** (`validate.py`) — row-count sanity checks, ISRC coverage
   percentage, orphan-reference checks. A load that fails validation must
   not be promoted — see `pipeline.py`'s `dry_run` gate.

`refresh.py` is the *only* module that calls the live MusicBrainz API, and
only for delta refreshes / targeted lookups / backfills of specific
recordings — never bulk search traffic — rate-limited to comply with
MusicBrainz's request policy.

## Integration boundary — needs Phase 0 verification

`transform.parse_dump_row()` is intentionally **not implemented**. This
pipeline's staging/transform/validate stages are written and tested against
the clean intermediate shapes in `transform.py` (`RawArtist`,
`RawRecording`, etc.), but MusicBrainz's actual dump file format (`mbdump`
tarball: is it plain COPY-format Postgres text per table, requiring
MusicBrainz's own schema to stage into first, or a simpler flat export?)
was not independently re-verified against the live current docs from this
environment — egress to musicbrainz.org was not exercised here. Confirm the
exact current dump format and column layout in Phase 0
(`docs/phase-0-checklist.md`) and implement `parse_dump_row()` against it —
do not treat the shapes below as verified fact.
