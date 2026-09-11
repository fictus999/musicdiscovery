"""fetch_real_catalog.py talks to the live musicbrainz.org API, which this
sandbox's network can't reach (see that module's docstring) — so these
mocks are shaped exactly like musicbrainzngs's real parsed responses
(verified against musicbrainzngs/mbxml.py's parse_recording/parse_track/
parse_medium/parse_release/parse_release_group directly, not guessed) to
catch data-assembly bugs without needing network access.

This test caught two real bugs during development: artist_credit and
medium rows staged without a `gid` silently produce zero rows in every
downstream table once loaded (transform.py's id-map join is `canonical.mbid
= staging.gid`, and NULL never equals NULL in SQL) — with no exception
raised anywhere. See fetch_real_catalog.py's _artist_credit_gid/_medium_gid
for the fix. This test only checks the dataset fetch_dataset() produces;
a companion integration test would be needed to catch a regression of the
NULL-gid bug itself (i.e. actually loading through transform.py), which
was verified manually against a live Postgres instance instead.
"""

import uuid
from unittest.mock import patch

import musicbrainzngs

import jobs.musicbrainz_ingest.fetch_real_catalog as frc


def _u(key: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, key))


def test_fetch_dataset_produces_non_null_gids_for_every_id_map_linked_table(monkeypatch):
    monkeypatch.setattr(frc, "ARTIST_NAMES", ["Artist A", "Artist B"])
    monkeypatch.setattr(frc, "RELEASE_GROUPS_PER_ARTIST", 1)
    monkeypatch.setattr(frc, "TRACKS_PER_RELEASE", 2)

    artist_mbids = {"Artist A": _u("artist:a"), "Artist B": _u("artist:b")}

    def fake_search_artists(artist=None, limit=None):
        mbid = artist_mbids[artist]
        return {"artist-list": [{"id": mbid, "name": artist, "sort-name": artist}]}

    def fake_browse_release_groups(artist=None, release_type=None, limit=None):
        return {
            "release-group-list": [
                {"id": _u(f"rg:{artist}"), "title": f"Album by {artist}", "primary-type": "Album", "first-release-date": "2001-05-01"}
            ]
        }

    def fake_browse_releases(release_group=None, includes=None, limit=None):
        rel_id = _u(f"rel:{release_group}")
        tracks = [
            {
                "id": _u(f"track:{release_group}:{i}"),
                "number": str(i),
                "position": i,
                "title": f"Track {i}",
                "recording": {
                    "id": _u(f"rec:{release_group}:{i}"),
                    "title": f"Track {i}",
                    "length": 200_000,
                    "isrc-list": [f"USRC{release_group[-4:]}{i}"],
                },
            }
            for i in range(1, 3)
        ]
        return {"release-list": [{"id": rel_id, "title": "Test Release", "barcode": None, "medium-list": [{"position": 1, "track-list": tracks}]}]}

    with patch.object(musicbrainzngs, "set_useragent"), \
         patch.object(musicbrainzngs, "search_artists", side_effect=fake_search_artists), \
         patch.object(musicbrainzngs, "browse_release_groups", side_effect=fake_browse_release_groups), \
         patch.object(musicbrainzngs, "browse_releases", side_effect=fake_browse_releases):
        dataset = frc.fetch_dataset()

    assert len(dataset["artist"]) == 2
    assert len(dataset["release_group"]) == 2
    assert len(dataset["recording"]) == 4
    assert len(dataset["track"]) == 4
    assert len(dataset["isrc"]) == 4

    # The bug this test exists to catch: every table transform.py links
    # through id_map (artist, artist_credit, release_group, release,
    # medium, recording, track's parents) must have a non-null gid, or
    # the real load silently drops everything downstream of it with no
    # error. artist_credit and medium are the two that don't have a
    # naturally-occurring MusicBrainz gid and need one synthesized.
    for row in dataset["artist_credit"]:
        assert row.get("gid"), "artist_credit row missing gid — will silently break every downstream table"
    for row in dataset["medium"]:
        assert row.get("gid"), "medium row missing gid — will silently break transform_tracks"
    for row in dataset["artist"]:
        assert row.get("gid")
    for row in dataset["release_group"]:
        assert row.get("gid")
    for row in dataset["recording"]:
        assert row.get("gid")

    # artist_credit gids must be deterministic (same artist -> same gid
    # every run) so re-running the fetch doesn't fork every artist_credit
    # into a new duplicate row via transform.py's `on conflict (mbid)`.
    first_run_gid = dataset["artist_credit"][0]["gid"]
    assert frc._artist_credit_gid(artist_mbids["Artist A"]) == first_run_gid
