# Phase 0 checklist

Tracks every "must verify before production reliance" item raised across the spec
revisions (V2 → V2.2) and the paid-Postgres architecture decision. Nothing here blocks
Phase 1 scaffolding (schema, provider interfaces, mocked adapters) — see
`docs/architecture.md` section E and the repo's own "parallel work" split. Items marked
**Blocks Phase 1 go-live** must clear before Phase 1 is exposed to real users; the rest
gate Phase 2 or general production launch.

| # | Item | Status | Blocks Phase 1 go-live? |
|---|---|---|---|
| 1 | Spotify Developer dashboard: confirm current quota mode, allowed users, scopes, and which endpoints actually respond for this app | Open — requires a real Spotify developer account | Only for the Authorization Code (connected-account) path; Client Credentials catalog resolution is unaffected |
| 2 | Apple Developer Program enrollment + MusicKit entitlement/catalog capability confirmation | Open — requires Apple Developer Program enrollment ($99/yr) | No — Apple provider is fully stubbed in Phase 1 |
| 3 | Artwork coverage/fallback plan: assuming item 12's license question clears, how much of the target catalog Cover Art Archive actually covers, and which listening-provider fields are usable as fallback | Open, and moot until item 12 clears | No — `artwork_url` stays null until resolved |
| 4 | MusicBrainz CC0 / CC BY-NC-SA boundary | **Resolved** — confirmed via the project's own Phase 0 research: core entity data is CC0, supplementary/tag/genre/annotation/edit-history data is CC BY-NC-SA (non-commercial). See `docs/architecture.md` section F. This session still hasn't independently read the primary license page itself (egress-blocked) — the resolution rests on the project's research, not this session's verification. | No longer blocking — schema already excludes everything but core CC0 tables |
| 5 | Genre/style similarity data source | Open — MusicBrainz's own tag data is CC BY-NC-SA (non-commercial), confirmed excluded per item 4; no replacement source picked yet | No for Phase 1 (genre dimension simply renormalizes away); **yes before any "genre" similarity mode ships** |
| 6 | Lyrics/theme data source (licensed lyrics or lawful semantic representation) | Open, unchanged from V2 | No — out of Phase 1 scope |
| 7 | Audio feature data source (BPM/energy/valence/etc., now that Spotify's are unavailable to new apps) | Open, unchanged from V2 | No — Phase 1 is metadata-only by design |
| 8 | Database capacity benchmark: run the full measurement plan in `docs/architecture.md` section G against a real ingestion, to produce the section H figure this checklist's infra sign-off (item 10) depends on | Open — no dry run has been executed yet. Reference facts now available (40M recordings / 57M tracks / 65M relationships, ~7GB compressed core dump, MusicBrainz recommends 60GB+ for a *full* replica) but our ~15-table subset's actual size is not yet measured | **Yes** — blocks finalizing the paid Postgres tier (item 10) and blocks treating the migrations as final (see `docs/architecture.md`'s provisional-status banner) |
| 9 | Confirm current MusicBrainz dump tarball list and which ones carry `release_group_meta`, `isrc`, `l_recording_work` (core `mbdump.tar.bz2` vs. a derived tarball), and the exact extracted file paths | Partially resolved — core `mbdump` confirmed as the canonical ingestion source and current schema version (31) confirmed per the project's Phase 0 research; the precise per-table tarball/path assignment is still unconfirmed | **Yes** — the ingestion pipeline's acquisition step needs this before it can run for real |
| 10 | Managed PostgreSQL budget sign-off | Open — blocked on item 8's benchmark; do not assume Supabase Pro's included 8GB is sufficient (see `docs/architecture.md` section D) | **Yes** — Phase 1 go-live needs a real database, not a local one |
| 11 | Spotify Premium-subscription-holding developer account established as a company/project asset, not an individual's personal login | Open, unchanged from V2.1 | Only for the Authorization Code path |
| 12 | Cover Art Archive commercial-use/license position | Open — **explicit go-live blocker**. CAA's redistribution/commercial terms are separate from MusicBrainz's CC0 core-data grant and must not be assumed to inherit it. See `docs/architecture.md` section F. | **Yes** — no CAA data may be cached or served commercially until resolved; `artwork_url` stays null until then regardless of what `ArtworkProvider`'s code supports |
| 13 | MetaBrainz Live Data Feed license position | Open — this is a distinct commercial MetaBrainz product from the static CC0 dump downloads; its terms have not been evaluated and must not be assumed compatible with the CC0 grant this project relies on for the static dumps | No for Phase 1 (not in use — refresh.py uses the rate-limited public API for targeted lookups only, not the Live Data Feed); blocks adoption if a future delta-refresh redesign considers it |
| 14 | MetaBrainz commercial account/support relationship documented | Open — not legally required for CC0 core-data use, but tracked as a decision this project should make deliberately given how central the dependency is | No — informational/operational, not a legal blocker |

## What "verified" means here

Two domains this project depends on — `developer.spotify.com` and `musicbrainz.org` —
are both blocked by this coding session's network egress proxy, so nothing in this
project has been confirmed by *this session* directly reading either site's current
documentation. Items 4 and 9 have since been substantially resolved anyway, through the
project's own Phase 0 research outside this session (real dataset scale, dump size,
schema version, and the CC0/CC BY-NC-SA boundary) — that's a materially stronger basis
than this session's earlier secondary-source corroboration, and those items are updated
above accordingly. What's still open and specifically needs someone on this project (not
this session) to check a primary source: item 1 (Spotify dashboard), item 12 (Cover Art
Archive's own terms — a different page from MusicBrainz's own data license), and item 13
(MetaBrainz's Live Data Feed product terms, again a different page from the one that
resolved item 4). Resolving MusicBrainz's *core data* license does not resolve any of
these three — each is its own source with its own terms, which is the entire point of
the commercial data policy in `docs/architecture.md` section F.
