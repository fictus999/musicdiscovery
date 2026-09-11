from collections.abc import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from app.config import settings

_engine: Engine | None = None

# Must match the search_path each migration file sets (database/migrations/
# 002-007) — music_catalog holds the MusicBrainz-derived canonical catalog,
# app holds everything application-specific, both in the same database.
# Setting this here means every query elsewhere in the codebase can keep
# using bare table names (recording, saved_songs, ...) without schema
# qualification; Postgres resolves each name against this path in order.
# No spaces around the commas: this string is passed through libpq's
# "options" connection parameter, which splits on whitespace before handing
# arguments to the server — "music_catalog, app, public" becomes three
# broken tokens ("music_catalog,", "app,", "public") instead of one -c flag.
SEARCH_PATH = "music_catalog,app,public"


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            connect_args={"options": f"-c search_path={SEARCH_PATH}"},
        )
    return _engine


def get_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session
