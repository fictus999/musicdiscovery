"""Orchestrates download -> stage -> transform -> validate. A failed
validation halts before anything is promoted into the tables the running
application actually queries — see validate.ValidationReport.passed.

This is the entry point Phase 1 ops would invoke (as a one-off bootstrap
job and, later, a scheduled refresh); it is not executed as part of this
scaffold since it depends on the unresolved parse_dump_row boundary (see
README.md) and on real infrastructure (remote compute, a real Postgres
instance) neither of which this sandbox has.
"""

import logging

from sqlalchemy import text
from sqlalchemy.engine import Engine

from .config import IngestConfig
from .download import download_dump
from .staging import STAGING_TABLES, ensure_staging_schema, load_table
from .validate import ValidationReport, run_validation

logger = logging.getLogger(__name__)


class IngestionFailed(Exception):
    def __init__(self, report: ValidationReport):
        self.report = report
        super().__init__(f"validation failed: {report.errors}")


def run_bootstrap_ingest(engine: Engine, config: IngestConfig, archive_filename: str) -> ValidationReport:
    archive = download_dump(archive_filename, config)
    if not archive.verified:
        raise RuntimeError(f"checksum verification failed for {archive_filename}; refusing to stage")

    with engine.begin() as conn:
        ensure_staging_schema(conn, config)
        # NOTE: extracting `archive.path` into per-table line iterables and
        # calling load_table(...) for each of STAGING_TABLES is the next
        # step here, once parse_dump_row (transform.py) is implemented
        # against the verified current dump format.
        logger.info("staging schema ready at %s; table load left to the caller pending parse_dump_row", config.staging_schema)

    with engine.connect() as conn:
        report = run_validation(conn)

    if not report.passed:
        raise IngestionFailed(report)

    with engine.begin() as conn:
        for table in ("artist", "release_group", "release", "work", "recording", "recording_external_ids"):
            conn.execute(text(f"analyze {table}"))

    logger.info("ingestion validated and promoted: %s", report.row_counts)
    return report
