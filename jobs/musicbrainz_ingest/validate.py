"""Post-load sanity checks. A load that fails these must not be promoted —
pipeline.py treats any non-empty `errors` list as a hard stop.
"""

from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.engine import Connection

# Below this, something is almost certainly wrong with the parse/transform
# step rather than with MusicBrainz's own data — ISRCs are near-ubiquitous
# for commercially released recordings.
MIN_EXPECTED_ISRC_COVERAGE = 0.30


@dataclass
class ValidationReport:
    row_counts: dict[str, int] = field(default_factory=dict)
    isrc_coverage: float = 0.0
    orphaned_recording_artists: int = 0
    orphaned_release_recordings: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.errors


def run_validation(conn: Connection) -> ValidationReport:
    report = ValidationReport()

    for table in ("artist", "release_group", "release", "work", "recording"):
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

    report.orphaned_recording_artists = conn.execute(
        text(
            "select count(*) from recording_artists ra "
            "left join artist a on a.id = ra.artist_id where a.id is null"
        )
    ).scalar_one()
    if report.orphaned_recording_artists:
        report.errors.append(f"{report.orphaned_recording_artists} recording_artists rows reference a missing artist")

    report.orphaned_release_recordings = conn.execute(
        text(
            "select count(*) from release_recordings rr "
            "left join recording r on r.id = rr.recording_id where r.id is null"
        )
    ).scalar_one()
    if report.orphaned_release_recordings:
        report.errors.append(
            f"{report.orphaned_release_recordings} release_recordings rows reference a missing recording"
        )

    return report
