"""Stage -> canonical transform.

The intermediate `Raw*` shapes below are what a dump parser must produce.
Everything downstream of them (dedup, normalization, upsert-row building)
is implemented and unit-tested against these shapes. `parse_dump_row` is
the one function that turns actual dump bytes into these shapes, and it is
deliberately NOT implemented — see README.md's "Integration boundary".
"""

from dataclasses import dataclass, field

from app.catalog.normalize import normalize_artist, normalize_title


@dataclass(frozen=True)
class RawArtist:
    mbid: str
    name: str
    sort_name: str | None = None
    disambiguation: str | None = None
    country: str | None = None
    artist_type: str | None = None


@dataclass(frozen=True)
class RawReleaseGroup:
    mbid: str
    title: str
    primary_type: str | None = None
    first_release_date: str | None = None  # ISO date string, may be partial (year-only)


@dataclass(frozen=True)
class RawRelease:
    mbid: str
    release_group_mbid: str | None
    title: str
    release_date: str | None = None
    country: str | None = None
    status: str | None = None
    barcode: str | None = None


@dataclass(frozen=True)
class RawWork:
    mbid: str
    title: str
    work_type: str | None = None
    language: str | None = None


@dataclass(frozen=True)
class RawRecording:
    mbid: str
    title: str
    length_ms: int | None
    artist_mbids: list[str] = field(default_factory=list)
    work_mbids: list[str] = field(default_factory=list)
    isrcs: list[str] = field(default_factory=list)


def parse_dump_row(table_name: str, raw_line: str) -> object:
    """Turn one raw dump-file row into the corresponding Raw* dataclass.

    NOT IMPLEMENTED: MusicBrainz's current dump file format/column layout
    was not independently re-verified against the live docs from this
    environment. Confirm it in Phase 0 (musicbrainz.org/doc/MusicBrainz_Database)
    and implement this against the real format rather than a guessed one —
    an ingestion pipeline that silently mis-parses columns is worse than one
    that doesn't run yet.
    """
    raise NotImplementedError(
        f"parse_dump_row for table '{table_name}' requires the current MusicBrainz dump "
        "format, verified in Phase 0. See jobs/musicbrainz_ingest/README.md."
    )


def build_artist_row(raw: RawArtist) -> dict:
    return {
        "mbid": raw.mbid,
        "name": raw.name,
        "sort_name": raw.sort_name,
        "normalized_name": normalize_artist(raw.name),
        "disambiguation": raw.disambiguation,
        "country": raw.country,
        "artist_type": raw.artist_type,
    }


def build_release_group_row(raw: RawReleaseGroup) -> dict:
    return {
        "mbid": raw.mbid,
        "title": raw.title,
        "normalized_title": normalize_title(raw.title),
        "primary_type": raw.primary_type,
        "first_release_date": raw.first_release_date,
    }


def build_release_row(raw: RawRelease) -> dict:
    return {
        "mbid": raw.mbid,
        "release_group_mbid": raw.release_group_mbid,
        "title": raw.title,
        "normalized_title": normalize_title(raw.title),
        "release_date": raw.release_date,
        "country": raw.country,
        "status": raw.status,
        "barcode": raw.barcode,
    }


def build_work_row(raw: RawWork) -> dict:
    return {
        "mbid": raw.mbid,
        "title": raw.title,
        "normalized_title": normalize_title(raw.title),
        "work_type": raw.work_type,
        "language": raw.language,
    }


def build_recording_row(raw: RawRecording) -> dict:
    return {
        "mbid": raw.mbid,
        "title": raw.title,
        "normalized_title": normalize_title(raw.title),
        "length_ms": raw.length_ms,
        "artist_mbids": list(raw.artist_mbids),
        "work_mbids": list(raw.work_mbids),
        "external_ids": [{"id_type": "isrc", "value": isrc, "verified": True} for isrc in raw.isrcs],
    }
