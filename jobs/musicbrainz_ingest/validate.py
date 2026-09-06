"""Post-load sanity checks. A load that fails these must not be promoted —
pipeline.py treats any non-empty `errors` list as a hard stop.
"""

from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.engine import Connection

# Below this, something is almost certainly wrong with the transform step
# rather than with MusicBrainz's own data — ISRCs are near-ubiquitous for
# commercially released recordings.
MIN_EXPECTED_ISRC_COVERAGE = 0.30

CORE_TABLES = ("artist", "artist_credit", "artist_credit_name", "release_group", "release", "medium", "track", "recording", "work")


@dataclass
class ValidationReport:
    row_counts: dict[str, int] = field(default_factory=dict)
    isrc_coverage: float = 0.0
    orphaned_tracks: int = 0
    orphaned_artist_credit_names: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.errors


def run_validation(conn: Connection) -> ValidationReport:
    report = ValidationReport()

    for table in CORE_TABLES:
        count = conn.execute(text(f"select count(*) from {table}")).scalar_one()
        report.row_counts[table] = count
        if count == 0:
            report.errors.append(f"{table} is empty after load")

    total_recordings = report.row_counts.get("recording", 0)
    if total_recordings:
        isrc_count = conn.execute(
            text("select count(distinct recording_id) from recording_external_ids where id_type = 'isrc'")
        ).scalar_one()
        report.isrc_coverage = isrc_count / total_recordings
        if report.isrc_coverage < MIN_EXPECTED_ISRC_COVERAGE:
            report.errors.append(
                f"ISRC coverage {report.isrc_coverage:.1%} is below the "
                f"{MIN_EXPECTED_ISRC_COVERAGE:.0%} sanity floor — check the transform step"
            )

    report.orphaned_tracks = conn.execute(
        text(
            "select count(*) from track t "
            "left join recording r on r.id = t.recording_id "
            "left join medium m on m.id = t.medium_id "
            "where r.id is null or m.id is null"
        )
    ).scalar_one()
    if report.orphaned_tracks:
        report.errors.append(f"{report.orphaned_tracks} track rows reference a missing recording or medium")

    report.orphaned_artist_credit_names = conn.execute(
        text(
            "select count(*) from artist_credit_name acn "
            "left join artist a on a.id = acn.artist_id "
            "left join artist_credit ac on ac.id = acn.artist_credit_id "
            "where a.id is null or ac.id is null"
        )
    ).scalar_one()
    if report.orphaned_artist_credit_names:
        report.errors.append(
            f"{report.orphaned_artist_credit_names} artist_credit_name rows reference a missing artist or artist_credit"
        )

    return report
