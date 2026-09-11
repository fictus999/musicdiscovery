"""Builds a bounded, real MusicBrainz dataset for the beta-demo catalog by
calling the live musicbrainz.org web service API.

This is deliberately NOT run from the main development sandbox: that
environment's network egress is blocked from reaching musicbrainz.org (see
dev_fixture.py's docstring for the history). It's meant to run on a
GitHub Actions runner instead, which has ordinary internet access, and its
output (a JSON file shaped for load_real_catalog.py) is picked up from
there as a workflow artifact.

Scope, deliberately bounded — this is a demo catalog, not a MusicBrainz
mirror:
  - A short, fixed, well-known artist list (ARTIST_NAMES below), not a
    crawl or the full artist table.
  - A handful of studio albums per artist (RELEASE_GROUPS_PER_ARTIST),
    a handful of tracks per album (TRACKS_PER_RELEASE) — total output is
    on the order of a few hundred recordings, not MusicBrainz's ~40M.
  - No dump file is downloaded; every row here comes from paginated,
    rate-limited (~1 req/sec, enforced by the musicbrainzngs client)
    calls to the public /ws/2/ JSON API, respecting MusicBrainz's own
    API etiquette (descriptive User-Agent, no parallel requests).

Every gid in the output is a REAL MusicBrainz identifier (unlike
dev_fixture.py's synthetic uuid5 values) — this is real catalog data, just
a small slice of it, fetched live rather than assumed or fabricated.

A single artist/release/recording lookup failing (rate limit hiccup, an
artist search returning no match, a release with no ISRC on file, etc.)
must not abort the whole run — this appends what it can get and logs the
rest to stderr, since a partial real catalog beats no catalog.
"""

from __future__ import annotations

import itertools
import json
import os
import sys
import time
import uuid

import musicbrainzngs

# artist_credit has no meaningful real-world gid for a single-artist credit
# (MusicBrainz's own artist_credit.gid is typically NULL) — but
# transform.py's id-map linkage (_populate_id_map, transform.py) requires
# one: it resolves canonical ids by joining canonical.mbid = staging.gid,
# and NULL never equals NULL in SQL, so a staged artist_credit row with no
# gid silently produces zero rows in id_map, which then cascades into
# every downstream table (artist_credit_name, release_group, release, ...
# all end up empty with no error raised). Deriving a deterministic gid
# from the artist's own real mbid keeps this reproducible from real data
# without claiming it's a genuine MusicBrainz-issued identifier.
_ARTIST_CREDIT_GID_NAMESPACE = uuid.UUID("a71c5e00-0000-4000-8000-000000000000")


def _artist_credit_gid(artist_mbid: str) -> str:
    return str(uuid.uuid5(_ARTIST_CREDIT_GID_NAMESPACE, artist_mbid))


# Same NULL-gid trap as artist_credit above — media aren't a real
# MusicBrainz entity with a natural mbid either, but transform.py's
# id-map join needs a non-null one regardless. dev_fixture.py already
# established this pattern for its synthetic data; deriving it here from
# the real release mbid + medium position keeps it deterministic.
_MEDIUM_GID_NAMESPACE = uuid.UUID("a71c5e00-0000-4000-8000-000000000001")


def _medium_gid(medium_key: str) -> str:
    return str(uuid.uuid5(_MEDIUM_GID_NAMESPACE, medium_key))

# A short, deliberately diverse (era/genre) list of unambiguous, globally
# well-known artists — chosen so MusicBrainz's search-by-name top result
# is reliably the right entity, not because of any curation/"popular
# songs" catalog design decision (see docs/architecture.md's Commercial
# Data Policy section — this is demo-only, not the production ingestion
# design, which stays full-catalog per that doc).
ARTIST_NAMES = [
    "Daft Punk", "Radiohead", "Frank Ocean", "Tame Impala", "Beyoncé",
    "Kendrick Lamar", "Fleetwood Mac", "David Bowie", "Adele", "The Beatles",
    "Nirvana", "Miles Davis", "Aretha Franklin", "Bob Marley", "Queen",
    "Taylor Swift", "Kanye West", "Björk", "Pink Floyd", "Stevie Wonder",
    "Amy Winehouse", "The Weeknd", "Billie Eilish", "Prince", "Outkast",
    "Fela Kuti", "ABBA", "Massive Attack", "Portishead", "Daddy Yankee",
]

RELEASE_GROUPS_PER_ARTIST = int(os.environ.get("RELEASE_GROUPS_PER_ARTIST", "2"))
TRACKS_PER_RELEASE = int(os.environ.get("TRACKS_PER_RELEASE", "6"))
MAX_RECORDINGS = int(os.environ.get("MAX_RECORDINGS", "400"))
REQUEST_RETRY_ATTEMPTS = 2

_RELEASE_GROUP_TYPE_IDS = {"Album": 1, "Single": 2, "EP": 3}
RELEASE_GROUP_PRIMARY_TYPES = [{"id": v, "name": k} for k, v in _RELEASE_GROUP_TYPE_IDS.items()]
RELEASE_STATUSES = [{"id": 1, "name": "Official"}]
LANGUAGES = [{"id": 1, "iso_code_3": "eng", "name": "English"}]


def _log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def _call_with_retry(fn, *args, **kwargs):
    last_exc = None
    for attempt in range(REQUEST_RETRY_ATTEMPTS):
        try:
            return fn(*args, **kwargs)
        except musicbrainzngs.WebServiceError as exc:
            last_exc = exc
            _log(f"  retry {attempt + 1}/{REQUEST_RETRY_ATTEMPTS} after error: {exc}")
            time.sleep(2)
    raise last_exc


class _IdAllocator:
    def __init__(self):
        self._counter = itertools.count(1)
        self._by_mbid: dict[str, int] = {}

    def get_or_create(self, mbid: str) -> int:
        if mbid not in self._by_mbid:
            self._by_mbid[mbid] = next(self._counter)
        return self._by_mbid[mbid]

    def peek(self, mbid: str) -> int | None:
        return self._by_mbid.get(mbid)


def fetch_dataset() -> dict[str, list[dict]]:
    musicbrainzngs.set_useragent(
        "musicdiscovery-demo-catalog-fetch", "0.1", "https://github.com/fictus999/musicdiscovery"
    )

    artist_ids = _IdAllocator()
    artist_credit_ids = _IdAllocator()
    release_group_ids = _IdAllocator()
    release_ids = _IdAllocator()
    medium_ids = _IdAllocator()
    recording_ids = _IdAllocator()
    isrc_ids = itertools.count(1)

    dataset: dict[str, list[dict]] = {
        "artist": [],
        "artist_credit": [],
        "artist_credit_name": [],
        "release_group_primary_type": RELEASE_GROUP_PRIMARY_TYPES,
        "release_group": [],
        "release_group_meta": [],
        "release_status": RELEASE_STATUSES,
        "language": LANGUAGES,
        "release": [],
        "medium": [],
        "recording": [],
        "track": [],
        "isrc": [],
    }
    seen_recording_mbids: set[str] = set()

    for artist_name in ARTIST_NAMES:
        if len(dataset["recording"]) >= MAX_RECORDINGS:
            _log(f"hit MAX_RECORDINGS={MAX_RECORDINGS}, stopping")
            break

        _log(f"artist: {artist_name}")
        try:
            search_result = _call_with_retry(musicbrainzngs.search_artists, artist=artist_name, limit=1)
            matches = search_result.get("artist-list", [])
            if not matches:
                _log(f"  no artist match, skipping")
                continue
            mb_artist = matches[0]
        except Exception as exc:
            _log(f"  artist search failed, skipping: {exc}")
            continue

        artist_mbid = mb_artist["id"]
        artist_id = artist_ids.get_or_create(artist_mbid)
        dataset["artist"].append(
            {"id": artist_id, "gid": artist_mbid, "name": mb_artist["name"], "sort_name": mb_artist.get("sort-name", mb_artist["name"])}
        )
        ac_id = artist_credit_ids.get_or_create(artist_mbid)
        dataset["artist_credit"].append({"id": ac_id, "gid": _artist_credit_gid(artist_mbid), "name": mb_artist["name"]})
        dataset["artist_credit_name"].append(
            {"artist_credit": ac_id, "position": 0, "artist": artist_id, "name": mb_artist["name"], "join_phrase": ""}
        )

        try:
            rg_result = _call_with_retry(
                musicbrainzngs.browse_release_groups,
                artist=artist_mbid,
                release_type=["album"],
                limit=RELEASE_GROUPS_PER_ARTIST,
            )
            release_groups = rg_result.get("release-group-list", [])
        except Exception as exc:
            _log(f"  release-group browse failed, skipping artist: {exc}")
            continue

        for rg in release_groups:
            if len(dataset["recording"]) >= MAX_RECORDINGS:
                break
            rg_mbid = rg["id"]
            rg_id = release_group_ids.get_or_create(rg_mbid)
            type_name = rg.get("primary-type", "Album")
            first_release_date = rg.get("first-release-date", "")
            year = int(first_release_date[:4]) if first_release_date[:4].isdigit() else None

            dataset["release_group"].append(
                {"id": rg_id, "gid": rg_mbid, "name": rg["title"], "artist_credit": ac_id, "type": _RELEASE_GROUP_TYPE_IDS.get(type_name, 1)}
            )
            dataset["release_group_meta"].append(
                {"id": rg_id, "release_count": 1, "first_release_date_year": year, "first_release_date_month": None, "first_release_date_day": None}
            )

            try:
                rel_result = _call_with_retry(
                    musicbrainzngs.browse_releases,
                    release_group=rg_mbid,
                    includes=["media", "recordings", "isrcs"],
                    limit=1,
                )
                releases = rel_result.get("release-list", [])
            except Exception as exc:
                _log(f"  release browse failed for {rg['title']!r}, skipping: {exc}")
                continue
            if not releases:
                continue
            release = releases[0]
            release_mbid = release["id"]
            release_id = release_ids.get_or_create(release_mbid)
            dataset["release"].append(
                {
                    "id": release_id,
                    "gid": release_mbid,
                    "name": release.get("title", rg["title"]),
                    "artist_credit": ac_id,
                    "release_group": rg_id,
                    "status": 1,
                    "language": 1,
                    "barcode": release.get("barcode"),
                }
            )

            tracks_taken = 0
            for medium in release.get("medium-list", []):
                if tracks_taken >= TRACKS_PER_RELEASE:
                    break
                medium_mbid = f"{release_mbid}:{medium.get('position', 1)}"
                medium_id = medium_ids.get_or_create(medium_mbid)
                track_list = medium.get("track-list", [])
                dataset["medium"].append(
                    {
                        "id": medium_id,
                        "gid": _medium_gid(medium_mbid),
                        "release": release_id,
                        "position": int(medium.get("position", 1)),
                        "track_count": min(len(track_list), TRACKS_PER_RELEASE) or 1,
                    }
                )

                for track in track_list:
                    if tracks_taken >= TRACKS_PER_RELEASE or len(dataset["recording"]) >= MAX_RECORDINGS:
                        break
                    recording = track.get("recording")
                    if not recording:
                        continue
                    rec_mbid = recording["id"]
                    if rec_mbid in seen_recording_mbids:
                        continue
                    seen_recording_mbids.add(rec_mbid)
                    rec_id = recording_ids.get_or_create(rec_mbid)
                    length_ms = None
                    length_raw = track.get("length") or recording.get("length")
                    if length_raw is not None:
                        try:
                            length_ms = int(length_raw)
                        except (TypeError, ValueError):
                            length_ms = None

                    dataset["recording"].append(
                        {"id": rec_id, "gid": rec_mbid, "name": recording.get("title", track.get("title", "")), "artist_credit": ac_id, "length": length_ms, "video": False}
                    )
                    dataset["track"].append(
                        {
                            "id": rec_id,
                            "gid": track.get("id", rec_mbid),
                            "recording": rec_id,
                            "medium": medium_id,
                            "position": int(track.get("position", tracks_taken + 1)),
                            "number": str(track.get("number", tracks_taken + 1)),
                            "name": recording.get("title", track.get("title", "")),
                            "artist_credit": ac_id,
                            "length": length_ms,
                        }
                    )
                    for isrc in recording.get("isrc-list", []) or []:
                        dataset["isrc"].append({"id": next(isrc_ids), "recording": rec_id, "isrc": isrc})
                    tracks_taken += 1

    _log(
        f"done: {len(dataset['artist'])} artists, {len(dataset['release_group'])} release groups, "
        f"{len(dataset['recording'])} recordings, {len(dataset['isrc'])} isrcs"
    )
    return dataset


if __name__ == "__main__":
    output_path = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("OUTPUT_PATH", "demo_catalog.json")
    data = fetch_dataset()
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)
    _log(f"wrote {output_path}")
