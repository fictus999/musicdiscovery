# Architecture

This document is the canonical record of the Phase 1 architecture decisions, and why
each one was made. It supersedes any earlier informal description of the schema.

## A. Canonical entity/data model

The canonical catalog mirrors MusicBrainz's own entity graph, verified against the
`mbdata` package (MetaBrainz's own SQLAlchemy models, PyPI `mbdata==31.0.1`) rather than
assumed from memory — see "How this was verified" below.

```
artist ──┬── artist_credit_name ──── artist_credit ──┬── recording
         │                                            ├── release
         │                                            ├── release_group
         │                                            └── track
         │
work ── work_external_ids (ISWC)
  │
  └── recording_works (recording ↔ work, from MusicBrainz's l_recording_work)

release_group ── release ── medium ── track ── recording
                                                   │
                                                   ├── recording_external_ids (ISRC)
                                                   └── provider_track_mappings (Spotify/Apple)
```

Key correction from the first schema pass: **artist credit is its own entity**
(`artist_credit` + `artist_credit_name`), not a flat recording↔artist join. MusicBrainz
reuses a single `artist_credit` row (e.g. "Daft Punk feat. Pharrell Williams") across every
recording, release, and release_group that shares that exact credit — collapsing it into
a simple join table would lose the credited display name (which can differ from the
artist's canonical name) and the `join_phrase` between multiple credited artists (" feat. ",
" & ", etc.), and would require reconstructing both during every future re-ingestion. Same
logic for **medium/track as real entities distinct from recording**: a release has one or
more media (CD1, CD2, vinyl side), each with tracks in position order, and a track has its
own title/length that can differ from the recording it points to (a compilation can retitle
a track). Flattening this into a single `release_recordings` table, as the first pass did,
throws away information MusicBrainz's own dump provides for free.

### Tables

| Table | Purpose | Notes |
|---|---|---|
| `artist` | Canonical artist | `mbid` (gid), `name`, `sort_name`, `normalized_name`, `disambiguation` |
| `artist_credit` | A reusable credited-artist-string | `mbid`, `name` (rendered credit) |
| `artist_credit_name` | Position + artist + join_phrase within a credit | composite PK `(artist_credit_id, position)` |
| `release_group` | An "album" independent of specific editions | `mbid`, `title`, `primary_type`, `first_release_date_year/month/day` (denormalized from MusicBrainz's `release_group_meta`) |
| `release` | A specific edition/issue | `mbid`, `release_group_id`, `artist_credit_id`, `title`, `status`, `language`, `script`, `barcode` |
| `medium` | A disc/side within a release | `release_id`, `position`, `format`, `track_count` |
| `track` | A track within a medium | `mbid`, `medium_id`, `recording_id`, `position`, `number`, `title`, `artist_credit_id`, `length_ms` |
| `recording` | The audio-identity level | `mbid`, `artist_credit_id`, `title`, `length_ms`, `video` |
| `work` | The abstract composition | `mbid`, `title`, `work_type` |
| `work_languages` | Work ↔ language (many-to-many) | mirrors MusicBrainz's `work_language` |
| `recording_works` | Recording performs/derives-from work | mirrors `l_recording_work`; **not filtered by link_type** in Phase 1 (see Simplifications) |
| `recording_external_ids` | ISRC (and future identifiers) | `(id_type, value)` unique |
| `work_external_ids` | ISWC | same shape, for works |
| `catalog_sources`, `provider_track_mappings`, `artwork`, `catalog_search_cache` | Unchanged from the first pass | provider-adjacent, not MusicBrainz-shaped |

### Deliberate simplifications (and why)

- **No `area`/`country_area` modeling.** Artist birthplace/label country isn't used by
  any Phase 1 or Phase 2 feature; adding it means replicating MusicBrainz's area
  hierarchy for no product benefit yet.
- **No per-country release dates (`release_country`).** MusicBrainz can carry a different
  release date per country for the same release. Phase 1's "release period similarity"
  only needs one approximate year, so the schema uses `release_group.first_release_date_*`
  (MusicBrainz's own denormalized "first known release" field, from `release_group_meta`)
  rather than modeling every country/date pair. If a future feature needs "was this
  reissued in Japan in 1998," `release_country` gets added then, not now.
- **No genre/tag ingestion at all.** MusicBrainz's `recording_tag` / `release_group_tag`
  tables are exactly the folksonomy data licensed **CC BY-NC-SA 3.0 (non-commercial)** —
  confirmed via MusicBrainz's own data-license documentation. Ingesting them into a paid
  product would violate that license. `RankingFeatures.tag_ids` stays in the ranking code
  as an empty set for Phase 1; the weight-renormalization logic already handles that
  correctly (a missing feature family drops out instead of scoring as 0). Genre/style
  similarity needs its own, separately licensed source — see the Phase 0 checklist.
- **`recording_works` isn't filtered by MusicBrainz's `link_type`.** MusicBrainz relates
  recordings to works through its generic relationship system (`link` → `link_type`),
  which covers more relationship kinds than "performs this work" (e.g. samples, medleys).
  Phase 1 materializes all `l_recording_work` rows undifferentiated; narrowing to the
  specific "performance" link type(s) is a cheap follow-up once it matters for a feature.
- **No alias, annotation, rating, or edit-history tables.** These are exactly the tables
  the CC BY-NC-SA license covers — excluding them is both a licensing requirement and a
  scope cut in the same move.

### How this was verified

`developer.spotify.com` and `musicbrainz.org` are both blocked by this environment's
egress proxy, so the schema above was **not** confirmed by reading MusicBrainz's docs
pages directly. It was instead verified against `mbdata` (`pip install mbdata`, version
31.0.1), MetaBrainz's own maintained SQLAlchemy mirror of the real schema, read directly
from the installed package on disk (`site-packages/mbdata/models.py`) — an authoritative
primary source, just reached a different way than a docs fetch. The license breakdown
came from search-engine-aggregated summaries of `musicbrainz.org/doc/About/Data_License`,
which is a materially weaker source than reading the page itself. **Confirm the CC0 /
CC BY-NC-SA boundary directly against that page in Phase 0** before this schema is
treated as legally final — the summary is consistent across multiple independent
searches, but nobody on this project has read the primary source yet.

## B. Ingestion architecture

The first pass planned a per-line Python parser turning dump rows into dataclasses. That
was wrong: MusicBrainz's dump files are plain PostgreSQL `COPY`-format text, one file per
table, in the exact column order of MusicBrainz's own schema — they're meant to be loaded
with `COPY table FROM file`, not parsed line-by-line in application code. Reimplementing
that in Python would be slower, riskier, and pointless when Postgres already does it
natively.

Revised pipeline (`jobs/musicbrainz_ingest/`):

1. **Acquire** — download the dump tarball(s) (core `mbdump.tar.bz2` plus whichever
   derived tarballs carry `release_group_meta`, `isrc`, `l_recording_work`, etc.) to
   remote compute/object storage. Never the developer's Mac (point 5).
2. **Verify** — checksum against MusicBrainz's published `MD5SUMS`/`SHA256SUMS` before
   anything downstream trusts the file. (Already implemented and unchanged.)
3. **Decompress/stage** — extract the per-table dump files and `COPY` each directly into
   a `mb_staging` schema whose tables mirror the *real* MusicBrainz column layout for
   only the ~15 tables Phase 1 needs (listed above). This is a straight `COPY FROM`, not
   a custom parser — the dump's own format is untouched.
4. **Normalize** — compute `normalized_title`/`normalized_name` (existing
   `app/catalog/normalize.py`, unchanged) for every staged row that needs text matching.
5. **Foreign-key/reference validation** — check every staged FK (e.g. every
   `recording.artist_credit` resolves to a staged `artist_credit.id`) before promoting;
   MusicBrainz dumps are internally consistent, but a partial/interrupted download must
   not silently produce orphans downstream.
6. **ISRC/ISWC extraction** — staged `isrc`/`iswc` tables map directly onto
   `recording_external_ids`/`work_external_ids`.
7. **Canonical entity loading** — one SQL `INSERT ... SELECT` per canonical table,
   joining staged tables (e.g. `recording` ⋈ `artist_credit_name` ⋈ `artist`) into the
   shapes described in section A. This is where MusicBrainz's internal integer `id`s get
   translated to our own UUID primary keys, with the MusicBrainz `gid` kept as `mbid` for
   idempotent re-import (upsert on `mbid`, never duplicate on re-run).
8. **Indexes** — trigram/FTS indexes already exist as part of table DDL; this stage is
   just `ANALYZE` after a bulk load so the query planner has current statistics.
9. **Post-import validation** — row counts, ISRC coverage percentage, orphan checks
   (existing `validate.py`, unchanged in spirit, updated for the new table set). A load
   that fails validation is never promoted.

The live MusicBrainz API (rate-limited to ~1 req/sec) is reserved for exactly the
narrow cases in point 8 of the locked assumptions: delta refreshes between dumps,
targeted single-recording backfills, and maintenance lookups — never bulk search, which
always runs against our own indexed copy.

## C. Storage/indexing strategy

MusicBrainz's public statistics (as of a May 2026 snapshot; **[Likely]**, not
independently re-verified against `musicbrainz.org/statistics` directly due to the
egress block) put the dataset at roughly 2.8M artists, 5.4M releases, 38.7M recordings.
**[Guessing]**: for the ~15 tables Phase 1 actually ingests (excluding the much larger
full ~300-table MusicBrainz schema, and excluding the NC-licensed tag tables entirely),
a reasonable order-of-magnitude estimate is **20–60GB** including trigram/GIN indexes —
this is *not* a measured number and should not be treated as a budget commitment. The
first real ingestion dry run (Phase 1, against a disposable staging database) should
measure actual disk usage before the paid tier size is finalized.

Indexing:
- `gin_trgm_ops` trigram indexes on every `normalized_*` text column used for search
  (already in the migrations).
- Standard btree indexes on every foreign key (SQLAlchemy/Postgres default).
- A unique index on `(id_type, value)` for external IDs, and a partial index on ISRC
  specifically (already present) — this is the fast path canonical identity resolution
  depends on.
- `pgvector`'s ANN index is deliberately **not** created yet — an index over an empty
  `song_embeddings` table is dead weight, and ivfflat/hnsw tuning parameters need a real
  data distribution to choose sensibly. That's a Phase 2 migration.

## D. Required paid infrastructure components

- **Managed PostgreSQL sized for the estimate in section C**, not the Supabase free
  tier's 500MB. Recommendation: **stay on Supabase Pro** ($25/mo base, 8GB database
  included, $0.125/GB/month overage — confirmed current 2026 pricing) rather than
  migrating to a separate Postgres host immediately. At the 20–60GB estimate, overage
  is roughly $1.50–$6.50/month on top of the base plan — cheap enough that the
  integration convenience (Auth already lives there, one less service to operate) wins
  over a dedicated host for now. This is a "for now" call, not a permanent one — see
  point 4's portability requirement.
- **Schema stays vanilla, standard PostgreSQL** — no Supabase-proprietary extensions or
  RLS-dependent design for the catalog tables — so a later move to Neon, RDS, or another
  managed Postgres is a `pg_dump`/`pg_restore`, not a rewrite. (Neon's current storage
  price is $0.35/GB/month, roughly 3x Supabase's overage rate, though its scale-to-zero
  compute model can win for spiky traffic; AWS RDS has no free storage allowance and
  charges compute continuously. Neither is cheaper than Supabase Pro at this specific
  workload shape today — reassess if traffic patterns change.)
- **Remote compute for the ingestion job itself** (point 5) — a scratch VM or CI runner
  with enough disk to hold the downloaded dump + staging tables temporarily, writing
  finished canonical rows to the managed Postgres instance. Not sized yet; depends on
  which specific dump tarballs section B's step 1 ends up needing.
- **Object storage** for the raw dump archive (so re-runs of steps 3–9 don't require
  re-downloading), per the existing "large artifacts never live in Git or on the Mac"
  rule.

## E. Remaining Phase 0 decisions

See `docs/phase-0-checklist.md` for the full, trackable list. Summary of what changed
in this revision specifically:

- **Resolved**: canonical schema is reconciled around MusicBrainz's real entity model
  (this document, section A). Ingestion no longer assumes a Python line-parser; it uses
  native `COPY` staging (section B).
- **Newly identified, not resolved**: MusicBrainz's own tag/genre data is off-limits for
  commercial use (CC BY-NC-SA) — genre/style similarity has no data source yet and needs
  its own Phase 0 audit, separate from the artwork and lyrics sources already tracked.
- **Still open, unchanged**: Spotify/Apple dashboard verification, artwork source
  selection, MusicBrainz license boundary confirmed from the primary source page (not
  just search summaries), final ingestion compute sizing from a real dry run.
