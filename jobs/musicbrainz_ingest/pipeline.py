"""Orchestrates download -> stage (native COPY) -> transform (SQL + Python
normalization) -> validate. A failed validation halts before anything is
promoted into the tables the running application actually queries — see
validate.ValidationReport.passed.

This is the entry point Phase 1 ops would invoke (a one-off bootstrap job,
and later a scheduled delta refresh via refresh.py). It has been exercised
in this repository against small synthetic staging data to validate the
transform SQL end-to-end (see tests/integration/test_musicbrainz_ingest.py)
but not against a real multi-GB MusicBrainz dump — this sandbox has
neither the network access to musicbrainz.org nor the disk/compute budget
for that. Running it for real is a Phase 1 ops task, not something this
scaffold does on its own.
"""

import logging

from sqlalchemy import text
from sqlalchemy.engine import Engine

from .config import IngestConfig
from .download import download_dump
from .staging import copy_table_from_file, ensure_staging_schema
from .transform import transform_all
from .validate import ValidationReport, run_validation

logger = logging.getLogger(__name__)


class IngestionFailed(Exception):
    def __init__(self, report: ValidationReport):
        self.report = report
        super().__init__(f"validation failed: {report.errors}")


# dump table name -> the extracted file's path relative to the archive root.
# MusicBrainz's mbdump tarball extracts to `mbdump/<table>`; confirm this
# path and which tarball carries release_group_meta/isrc/l_recording_work
# in Phase 0 (see docs/phase-0-checklist.md item 9) before relying on it.
DUMP_FILE_PATHS = {table: f"mbdump/{table}" for table in [
    "artist", "artist_credit", "artist_credit_name",
    "release_group_primary_type", "release_group", "release_group_meta",
    "release_status", "language", "release", "medium", "track",
    "recording", "work", "work_language", "isrc", "iswc", "l_recording_work",
]}


def run_bootstrap_ingest(engine: Engine, dsn: str, config: IngestConfig, archive_filename: str, extracted_dir: str) -> ValidationReport:
    archive = download_dump(archive_filename, config)
    if not archive.verified:
        raise RuntimeError(f"checksum verification failed for {archive_filename}; refusing to stage")

    # Extraction (tar jxf) is left to the caller's ops tooling rather than
    # reimplemented here — it's a single well-understood shell step, and
    # this function's job is the parts that need application logic.
    ensure_staging_schema(dsn, config)
    for table, relative_path in DUMP_FILE_PATHS.items():
        copy_table_from_file(dsn, config, table, f"{extracted_dir}/{relative_path}")

    with engine.begin() as conn:
        counts = transform_all(conn, config.staging_schema, config.batch_size)
        logger.info("transform complete: %s", counts)

    with engine.connect() as conn:
        report = run_validation(conn)

    if not report.passed:
        raise IngestionFailed(report)

    with engine.begin() as conn:
        for table in ("artist", "artist_credit_name", "release_group", "release", "medium", "track", "recording", "work"):
            conn.execute(text(f"analyze {table}"))

    logger.info("ingestion validated and promoted: %s", report.row_counts)
    return report
