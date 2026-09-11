import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "apps" / "api"))

# Must be set before anything imports app.config (its Settings() singleton
# reads env vars once, at import time) — tests exercise the dev-mode auth
# path (X-User-Id header) rather than requiring a live Supabase project.
# See apps/api/app/auth.py and tests/unit/test_auth.py (the latter tests
# the *real* JWKS verification path directly, with a locally generated key,
# independent of this flag).
os.environ.setdefault("AUTH_DEV_MODE", "true")

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

# Overridable via env so CI (a different Postgres service container, likely
# different credentials/db name than this repo's local docker-compose
# setup) doesn't need to match this exact default. TEST_DSN is the same
# database in plain psycopg form (no `+psycopg` dialect suffix) for the
# ingestion pipeline's raw-psycopg calls (staging.py) — jobs/musicbrainz_ingest
# tests import it from here rather than hardcoding a second copy that could
# drift out of sync with TEST_DATABASE_URL.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/musicdiscovery_test"
)
TEST_DSN = TEST_DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")

# Must match apps/api/app/db/session.py's SEARCH_PATH — the migrations
# place tables in music_catalog/app, not public, so tests need the same
# resolution path the application uses.
_SEARCH_PATH_CONNECT_ARGS = {"options": "-c search_path=music_catalog,app,public"}

_TABLES_TO_TRUNCATE = (
    "recommendation_results",
    "recommendations",
    "model_versions",
    "saved_songs",
    "search_history",
    "app_users",
    "recording_external_ids",
    "work_external_ids",
    "recording_works",
    "track",
    "medium",
    "provider_track_mappings",
    "artwork",
    "recording",
    "release",
    "release_group",
    "work",
    "artist_credit_name",
    "artist_credit",
    "artist",
)


@pytest.fixture(scope="session")
def test_dsn():
    return TEST_DSN


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(TEST_DATABASE_URL, connect_args=_SEARCH_PATH_CONNECT_ARGS)
    try:
        with eng.connect() as conn:
            conn.execute(text("select 1"))
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"local Postgres test database unavailable: {exc}")
    yield eng
    eng.dispose()


@pytest.fixture
def db_session(engine):
    with Session(engine) as session:
        yield session
        session.rollback()
        with engine.begin() as conn:
            conn.execute(text(f"truncate {', '.join(_TABLES_TO_TRUNCATE)} cascade"))
