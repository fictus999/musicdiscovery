from dataclasses import dataclass


@dataclass(frozen=True)
class IngestConfig:
    dump_base_url: str = "https://data.metabrainz.org/pub/musicbrainz/data/fullexport/"
    checksum_filename: str = "MD5SUMS"
    download_dir: str = "/tmp/musicbrainz-dump"  # remote-compute scratch, never the local Mac (§20)
    staging_schema: str = "mb_staging"
    batch_size: int = 5_000
    # MusicBrainz's published request policy: ~1 request/second per IP with
    # an identifying User-Agent. refresh.py must not exceed this — verify
    # the current figure in Phase 0 rather than assuming it never changes.
    live_api_min_interval_seconds: float = 1.0
    user_agent: str = "music-discovery/0.1.0 (+contact: set MUSICBRAINZ_USER_AGENT env var)"
