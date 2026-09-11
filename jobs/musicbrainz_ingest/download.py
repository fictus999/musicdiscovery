"""Fetch a MusicBrainz dump archive and verify it against the published
checksum file before anything downstream trusts it. Runnable as written;
what's unverified from this environment is the exact current dump layout
(see transform.py / README.md), not this download/verify step.
"""

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin

import httpx

from .config import IngestConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DownloadedArchive:
    path: Path
    verified: bool


def _fetch(url: str, dest: Path, *, user_agent: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with httpx.stream("GET", url, headers={"User-Agent": user_agent}, follow_redirects=True, timeout=60.0) as resp:
        resp.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in resp.iter_bytes():
                f.write(chunk)


def _parse_md5sums(text: str) -> dict[str, str]:
    checksums: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        digest, _, filename = line.partition("  ")
        filename = filename.strip() or line.partition(" *")[2].strip()
        if digest and filename:
            checksums[filename] = digest
    return checksums


def _md5(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.md5()
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def download_dump(archive_filename: str, config: IngestConfig) -> DownloadedArchive:
    dest_dir = Path(config.download_dir)
    archive_path = dest_dir / archive_filename
    checksum_path = dest_dir / config.checksum_filename

    logger.info("downloading %s", archive_filename)
    _fetch(urljoin(config.dump_base_url, archive_filename), archive_path, user_agent=config.user_agent)
    _fetch(urljoin(config.dump_base_url, config.checksum_filename), checksum_path, user_agent=config.user_agent)

    checksums = _parse_md5sums(checksum_path.read_text())
    expected = checksums.get(archive_filename)
    if expected is None:
        logger.warning("no checksum entry for %s; refusing to mark as verified", archive_filename)
        return DownloadedArchive(path=archive_path, verified=False)

    actual = _md5(archive_path)
    verified = actual.lower() == expected.lower()
    if not verified:
        logger.error("checksum mismatch for %s: expected %s got %s", archive_filename, expected, actual)
    return DownloadedArchive(path=archive_path, verified=verified)
