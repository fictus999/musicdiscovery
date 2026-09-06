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
| 3 | Artwork source selection: Cover Art Archive coverage for the target catalog, plus which listening-provider fields are usable as fallback | Open | No — `artwork_url` stays null until resolved |
| 4 | MusicBrainz CC0 / CC BY-NC-SA boundary confirmed against the primary license page (`musicbrainz.org/doc/About/Data_License`), not just search-engine summaries | Partially resolved — summary is consistent across sources but the primary page itself hasn't been read (egress-blocked from this environment) | **Yes** — don't ingest anything beyond the core CC0 entity tables until this is confirmed directly |
| 5 | Genre/style similarity data source | **New** — MusicBrainz's own tag data is CC BY-NC-SA (non-commercial), so it's excluded from this schema entirely; no replacement source picked yet | No for Phase 1 (genre dimension simply renormalizes away); **yes before any "genre" similarity mode ships** |
| 6 | Lyrics/theme data source (licensed lyrics or lawful semantic representation) | Open, unchanged from V2 | No — out of Phase 1 scope |
| 7 | Audio feature data source (BPM/energy/valence/etc., now that Spotify's are unavailable to new apps) | Open, unchanged from V2 | No — Phase 1 is metadata-only by design |
| 8 | First real MusicBrainz ingestion dry run: measure actual disk usage against the 20–60GB estimate before finalizing paid Postgres tier size | Open — no dry run has been executed yet | **Yes** — the estimate in `docs/architecture.md` section C is explicitly not a budget commitment |
| 9 | Confirm current MusicBrainz dump tarball list and which ones carry `release_group_meta`, `isrc`, `l_recording_work` (core `mbdump.tar.bz2` vs. a derived tarball) | Open — inferred from `mbdata`'s schema mirror, not confirmed against the current `MusicBrainz_Database/Download` page (egress-blocked) | **Yes** — the ingestion pipeline's acquisition step needs this before it can run for real |
| 10 | Supabase Pro (or alternative managed Postgres) budget sign-off | Open — recommendation given in `docs/architecture.md` section D, not yet approved as spend | **Yes** — Phase 1 go-live needs a real database, not a local one |
| 11 | Spotify Premium-subscription-holding developer account established as a company/project asset, not an individual's personal login | Open, unchanged from V2.1 | Only for the Authorization Code path |

## What "verified" means here

Two domains this project depends on — `developer.spotify.com` and `musicbrainz.org` —
are both blocked by this environment's network egress proxy, so nothing in this project
has been confirmed by directly reading either site's current documentation from inside
this session. Everything sourced from them so far is either: (a) cross-referenced
against multiple independent secondary sources including dated blog posts and changelog
titles that match the real domain's URL structure, or (b) read from an authoritative
package (`mbdata`) maintained by the same organization, installed and inspected locally.
That's a reasonable basis for the architecture decisions made so far, but it is not the
same as someone on this project logging into the Spotify dashboard or reading
`musicbrainz.org/doc/About/Data_License` directly — items 4 and 9 specifically should be
the first ones closed, since they're cheap (reading a doc page, or the download page)
and currently rest on secondary-source corroboration rather than a primary read.
