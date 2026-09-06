# Architecture

This document is the canonical record of the Phase 1 architecture decisions, and why
each one was made. It supersedes any earlier informal description of the schema.

> **Status: provisional.** The canonical schema (section A) and the sizing in sections C/G/H
> are locked in shape but not in final capacity — the database-capacity benchmark (section G)
> has not been run yet. Do not treat the migrations in `database/migrations/` as final, and do
> not make further piecemeal schema changes until that benchmark and the commercial-data
> review (section F) both close. See `docs/phase-0-checklist.md` for exactly what's still open.

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

### Database topology: one instance, two schemas

**Decision**: one PostgreSQL database/instance for both the canonical catalog and the
application tables — not two separate databases. All of section A's tables live in a
`music_catalog` schema; `app_users`, `subscriptions`, `saved_songs`, `user_interactions`,
`recommendations`, and the rest of the application/behavioral tables live in an `app`
schema. Both schemas, one database, so:

- Foreign keys stay enforced across the split (`app.saved_songs.recording_id →
  music_catalog.recording.id` is a normal in-database FK — Postgres foreign keys work
  across schemas within one database; they do not work across separate databases).
- Transactions spanning both (e.g. "save a song" touching `saved_songs` and reading
  `recording`) stay single-transaction, no distributed-transaction complexity.
- At the target scale (1,000–5,000 initial users), splitting into physically separate
  databases now would add operational complexity (two connection pools, no cross-database
  FK integrity, more failure surface) without solving a problem this project actually has.

The separation is enforced by `search_path`, not by schema-qualifying every table
reference: each migration file sets `search_path` at its own top (`music_catalog, public`
for the catalog migrations, `app, music_catalog, public` for the application ones — see
`database/migrations/00*.sql`), and the application's database connection
(`apps/api/app/db/session.py`'s `SEARCH_PATH` constant) sets the same path, so every query
elsewhere in the codebase keeps using bare table names (`recording`, `saved_songs`, ...)
with no code changes. This was chosen over hand schema-qualifying every reference because
it achieves the same physical separation (`\dt music_catalog.*` vs `\dt app.*` show the
real split; a future `pg_dump -n music_catalog` extracts exactly the catalog) with far
less surface area for a mistake.

If scale or cost ever requires physically splitting the catalog onto its own database —
the reason this is schema-separated rather than left as one flat schema — that migration
starts from an already-clean boundary instead of picking tables out of a merged schema
after the fact.

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
pages directly from inside this session. It was instead verified against `mbdata`
(`pip install mbdata`, version 31.0.1), MetaBrainz's own maintained SQLAlchemy mirror of
the real schema, read directly from the installed package on disk
(`site-packages/mbdata/models.py`) — an authoritative primary source, just reached a
different way than a docs fetch. `mbdata`'s installed version (31) matches MusicBrainz's
current schema version (31, per the project's own Phase 0 research below), so there is no
version-skew concern between what was read and what production will ingest.

The CC0 / CC BY-NC-SA boundary, current dataset scale, and dump size (section C) have
since been confirmed through the project's own Phase 0 research (see
`docs/phase-0-checklist.md`) rather than this session's search-summary corroboration —
those figures now supersede the earlier `[Likely]`/`[Guessing]`-tagged estimates. What
still hasn't been independently read by this session specifically is the exact dump
tarball layout (which archive carries `release_group_meta`/`isrc`/`l_recording_work`, and
the precise extracted file paths) — tracked as `docs/phase-0-checklist.md` item 9.

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

Per the project's Phase 0 research (superseding this session's earlier search-summary
estimate): the current MusicBrainz database holds roughly **40M recordings, 57M tracks,
and 65M relationships**; the core dump compresses to roughly **7GB**; MusicBrainz's own
server documentation recommends **60GB+ free disk for a full database** (all ~300 tables,
including edit history, annotations, and every vocabulary table); current schema version
is **31** (matching the installed `mbdata==31.0.1` used to verify section A).

That 60GB figure is a ceiling for the *full* replica, not for the ~15-table subset this
project ingests (core entity tables only — no tags, annotations, ratings, or edit
history, all of which are excluded on licensing grounds regardless of size; see section F).
**How much smaller our subset is than 60GB is not yet known** — estimating a fraction
from the outside would be exactly the kind of unmeasured assumption this project has
already been burned by twice (the Spotify quota assumption, the first-pass ingestion
design). Section G defines how that number gets measured for real instead.

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

## D. Infrastructure: $0 development, paid production

Development and production are deliberately different infrastructure, on purpose, not
because of a shortcut: this section covers production; local/CI development runs
entirely on unpaid infrastructure, documented in `README.md`'s local-development section
and `docker-compose.yml`. Concretely: a single Dockerized PostgreSQL
(`pgvector/pgvector:pg16`, one instance, `music_catalog`/`app` schemas per the topology
above) for a developer's machine, the same image as a GitHub Actions service container
for CI, and a small hand-authored fixture (`jobs/musicbrainz_ingest/dev_fixture.py` —
**not** a filtered "popular songs" production catalog; see that module's docstring) run
through the real ingestion pipeline instead of the full MusicBrainz dump. None of this
requires Supabase Pro, a managed Postgres tier, or any spend — Supabase Free may still be
used for Auth during development, but it is not where the catalog lives even in dev,
consistent with the production topology below.

### Required paid infrastructure components (production only)

- **Managed PostgreSQL**, not the Supabase free tier's 500MB — mandatory from Phase 1
  regardless of exact size. **Do not assume Supabase Pro's included 8GB is sufficient**;
  section C's "how much smaller than 60GB" question is unresolved, and the overage math
  only becomes a real decision once section G's benchmark produces an actual number.
  Provisional direction (not a sizing commitment): Supabase Pro remains the leading
  candidate over standing up a separate Postgres host immediately, purely on integration
  grounds (Auth already lives there, one less service to operate) — but if the benchmark
  comes back large enough that Supabase's per-GB overage rate stops being the cheapest
  option (a real possibility MusicBrainz's own 60GB full-replica figure raises), a
  dedicated host is back on the table. That comparison is deferred to section H, not
  decided here.
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
  native `COPY` staging (section B). CC0 core / CC BY-NC-SA supplementary boundary,
  current dataset scale, and core dump size are now confirmed via the project's own
  Phase 0 research (section C).
- **Newly identified, not resolved**: Cover Art Archive's commercial-use position is
  separate from MusicBrainz's core-data CC0 grant and has not been confirmed (section F)
  — no CAA data may be ingested into the commercial database until it is. Same for
  MetaBrainz's Live Data Feed, which is a distinct commercial product from the static CC0
  dump snapshots and carries its own terms.
- **Still open, unchanged**: Spotify/Apple dashboard verification, artwork source
  selection (blocked on the CAA question above), exact dump tarball/file-path layout,
  and — the new blocking item — the database capacity benchmark (section G) that
  section C's storage estimate depends on.

## F. Commercial data policy

Every data source this project touches has a different commercial-use position. Treating
them as one undifferentiated "MusicBrainz data" bucket is exactly the mistake that would
have shipped a license violation in the first schema pass (tag/genre data). This table is
the single place that distinction is tracked; nothing overrides it without an explicit
update here.

| Source | License / commercial status | Ingestion status |
|---|---|---|
| **MusicBrainz core entity data** (artist, release, recording, release_group, work, ISRC, ISWC, and the relationships between them) | **CC0** — public domain, no attribution required, unrestricted commercial use. Confirmed via the project's Phase 0 research. | **Permitted, and the only data this schema ingests today** (section A's tables). |
| **MusicBrainz supplementary/tag/genre data** (`recording_tag`, `release_group_tag`, `annotation`, `rating`, edit history, and similar) | **CC BY-NC-SA 3.0 — non-commercial.** Attribution + share-alike required even for the permitted non-commercial uses. | **Excluded entirely** from the canonical catalog. Not staged, not transformed, not queried. Would need a separate commercial license from MetaBrainz to use at all — not attempted in Phase 1. |
| **MetaBrainz Live Data Feed** (near-real-time replication service, a distinct paid MetaBrainz product from the static dump downloads) | **Not established.** Its terms are commercial-product terms, not an extension of the CC0 grant on the static dumps — the two must not be conflated. | **Not in use, and not assumed usable.** If a future delta-refresh need makes the Live Data Feed attractive (versus this project's own scheduled dump-based refresh), its licensing/pricing must be evaluated on its own before adoption. |
| **Cover Art Archive** | **Not established for this project's commercial use.** CAA is operated by the Internet Archive in partnership with MetaBrainz; its image content's redistribution/commercial-use terms have not been confirmed and must not be assumed to inherit MusicBrainz's own CC0 status. | **Blocked.** No CAA-sourced artwork may be cached, stored, or served by this product until this is resolved — see `docs/phase-0-checklist.md`. `ArtworkProvider`'s Cover-Art-Archive adapter exists in code as an interface implementation, not a green light to store its output commercially. |
| **Provider artwork** (Spotify/Apple album art surfaced through their own catalog APIs) | Governed by each provider's own developer terms (Spotify Developer Policy, Apple Developer Program License Agreement), not MusicBrainz's license at all. | Same status as every other Spotify/Apple catalog use in this project: permitted only within whatever Client-Credentials-scoped catalog terms Phase 0's provider-dashboard review confirms — not yet independently verified (see `docs/phase-0-checklist.md`). |

**MetaBrainz commercial account/support status**: whether this project has, or needs, a
formal commercial relationship with MetaBrainz (their own site invites commercial users to
"contact them" for licensing beyond the free CC0 dumps, and separately sells Live Data Feed
access) is tracked but not yet decided — see `docs/phase-0-checklist.md` item 13.
Nothing above requires it for the CC0 core data (CC0 already permits unrestricted
commercial use with no account needed), but a documented relationship may still be the
right move for support/reliability reasons on a production dependency this central.

## G. Database capacity benchmark plan

Section C deliberately stops short of a final storage number. This is the plan for
producing one, to run during Phase 1's first real ingestion attempt (not before — it
needs the actual dump, which needs remote compute per point 9's "never the developer's
Mac" rule). Every measurement below should be recorded, not just the final figure — a
number with no breakdown can't be sanity-checked when the dataset grows.

1. **Compressed dump size** — the downloaded tarball(s) as fetched. Sanity check against
   the ~7GB core-dump figure in section C; a large deviation means the wrong tarball, a
   schema-version mismatch, or a MusicBrainz-side dataset-size change worth re-noting here.
2. **Uncompressed staging size** — total size of `mb_staging.*` after `COPY` load, before
   any transform runs. This is the "remote compute needs at least this much scratch disk"
   number (point 9 of the locked assumptions).
3. **PostgreSQL heap size** — `pg_total_relation_size` (excluding indexes) summed across
   the canonical tables in section A, immediately after the transform step, before
   `ANALYZE`/index rebuild.
4. **Index size** — trigram/GIN and btree index size, separately from heap size (Postgres
   reports these independently; conflating them hides which one to tune if either grows
   disproportionately). Trigram indexes in particular can be a large multiple of the
   underlying text column size — measure, don't assume a ratio.
5. **WAL/temp space requirements** — peak WAL generation and any `work_mem`-driven temp
   file usage during the bulk transform (large batched `INSERT ... ON CONFLICT` and the
   `id_map`-joined `SELECT`s in `transform.py` are the likely peak consumers). This is a
   *transient* requirement (during ingestion, not steady-state), but the paid tier still
   needs enough headroom to survive it without throttling mid-import.
6. **Final database size** — heap + indexes + any residual staging-schema data not yet
   dropped, at rest, after a completed and validated import.
7. **Expected growth** — MusicBrainz's dataset grows continuously (new releases added
   daily); a delta refresh (point 8 of the locked assumptions, via `refresh.py`) adds
   incrementally rather than re-importing from scratch, but the growth *rate* — how much
   the database grows per month of MusicBrainz's own growth — should be estimated from
   two dump versions a known interval apart once that data point exists, not guessed.

## H. Minimum production PostgreSQL capacity

**Not yet defined — deliberately.** Section E of the locked assumptions is explicit that
this must come from measurement (section G), not assumption; committing to a number now
would repeat the exact mistake section C's superseded 20–60GB guess was. Once section G's
benchmark runs, this section gets replaced with: a specific minimum storage figure (final
database size + a growth buffer sized from the measured growth rate, not a round-number
guess), the corresponding Supabase Pro overage cost (or the alternative-provider comparison
from section D if Supabase stops being cheapest at that size), and the compute/scratch-disk
spec for the remote ingestion host from section G's steps 1–2. Until then, treat any
capacity number mentioned elsewhere in this project as provisional.
