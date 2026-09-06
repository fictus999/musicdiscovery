import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "apps" / "api"))

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

TEST_DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/musicdiscovery_test"

_TABLES_TO_TRUNCATE = (
    "recommendation_results",
    "recommendations",
    "model_versions",
    "saved_songs",
    "app_users",
    "recording_external_ids",
    "release_recordings",
    "recording_works",
    "recording_artists",
    "provider_track_mappings",
    "artwork",
    "recording",
    "release",
    "release_group",
    "work",
    "artist",
)


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(TEST_DATABASE_URL)
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
