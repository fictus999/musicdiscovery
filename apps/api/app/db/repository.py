"""Read/write access to the canonical catalog and app tables, on top of
which recommendation/service.py and the routes are built. Kept separate
from MusicBrainzCatalogProvider (which answers search/identity questions
a CatalogProvider is meant to answer) — this module is app-schema-shaped
(RankingFeatures, SongDTO), not catalog-provider-interface-shaped.
"""

import json

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.recommendation.baseline_ranking import RankingFeatures
from contracts import ProviderLink, SongDTO

_RANKING_FEATURES_SQL = text(
    """
    select r.id as recording_id,
           r.identity_confidence,
           array_agg(distinct acn.artist_id::text) as artist_ids,
           (select min(rg.first_release_date_year)
              from track t
              join medium m on m.id = t.medium_id
              join release rel on rel.id = m.release_id
              join release_group rg on rg.id = rel.release_group_id
             where t.recording_id = r.id) as release_year,
           (select min(rel.language)
              from track t
              join medium m on m.id = t.medium_id
              join release rel on rel.id = m.release_id
             where t.recording_id = r.id) as language
    from recording r
    join artist_credit_name acn on acn.artist_credit_id = r.artist_credit_id
    where r.id = :recording_id
    group by r.id, r.identity_confidence
    """
)

_CANDIDATE_IDS_BY_SHARED_ARTIST_SQL = text(
    """
    select distinct r2.id
    from artist_credit_name acn1
    join recording r1 on r1.artist_credit_id = acn1.artist_credit_id
    join artist_credit_name acn2 on acn2.artist_id = acn1.artist_id
    join recording r2 on r2.artist_credit_id = acn2.artist_credit_id and r2.id <> r1.id
    where r1.id = :recording_id
    limit :limit
    """
)

_SONG_DTO_SQL = text(
    """
    select r.id as recording_id, r.title, r.length_ms,
           array_agg(distinct coalesce(nullif(acn.name, ''), a.name)) as artist_names
    from recording r
    join artist_credit_name acn on acn.artist_credit_id = r.artist_credit_id
    join artist a on a.id = acn.artist_id
    where r.id = :recording_id
    group by r.id, r.title, r.length_ms
    """
)


def get_ranking_features(session: Session, recording_id: str) -> RankingFeatures | None:
    row = session.execute(_RANKING_FEATURES_SQL, {"recording_id": recording_id}).mappings().first()
    if row is None:
        return None
    return RankingFeatures(
        recording_id=str(row["recording_id"]),
        artist_ids=frozenset(row["artist_ids"] or []),
        release_year=row["release_year"],
        language=row["language"],
        identity_confidence=float(row["identity_confidence"]),
    )


def get_candidate_ids_by_shared_artist(session: Session, recording_id: str, limit: int = 200) -> list[str]:
    rows = session.execute(
        _CANDIDATE_IDS_BY_SHARED_ARTIST_SQL, {"recording_id": recording_id, "limit": limit}
    ).all()
    return [str(row[0]) for row in rows]


def get_ranking_features_bulk(session: Session, recording_ids: list[str]) -> dict[str, RankingFeatures]:
    """Batched form of get_ranking_features — avoids N+1 queries when
    scoring a whole candidate pool (Phase 2's larger candidate pools will
    need this even more; Phase 1's shared-artist pool is small enough that
    either approach works, but there's no reason to write the N+1 version
    first and fix it later).
    """
    if not recording_ids:
        return {}
    rows = session.execute(
        text(
            """
            select r.id as recording_id,
                   r.identity_confidence,
                   array_agg(distinct acn.artist_id::text) as artist_ids,
                   (select min(rg.first_release_date_year)
                      from track t
                      join medium m on m.id = t.medium_id
                      join release rel on rel.id = m.release_id
                      join release_group rg on rg.id = rel.release_group_id
                     where t.recording_id = r.id) as release_year,
                   (select min(rel.language)
                      from track t
                      join medium m on m.id = t.medium_id
                      join release rel on rel.id = m.release_id
                     where t.recording_id = r.id) as language
            from recording r
            join artist_credit_name acn on acn.artist_credit_id = r.artist_credit_id
            where r.id = any(:recording_ids)
            group by r.id, r.identity_confidence
            """
        ),
        {"recording_ids": recording_ids},
    ).mappings().all()
    return {
        str(row["recording_id"]): RankingFeatures(
            recording_id=str(row["recording_id"]),
            artist_ids=frozenset(row["artist_ids"] or []),
            release_year=row["release_year"],
            language=row["language"],
            identity_confidence=float(row["identity_confidence"]),
        )
        for row in rows
    }


def get_song_dto(session: Session, recording_id: str, *, provider_links: list[ProviderLink] | None = None) -> SongDTO | None:
    row = session.execute(_SONG_DTO_SQL, {"recording_id": recording_id}).mappings().first()
    if row is None:
        return None
    return SongDTO(
        recording_id=str(row["recording_id"]),
        title=row["title"],
        artist_names=list(row["artist_names"]),
        length_ms=row["length_ms"],
        provider_links=provider_links or [],
    )


def get_or_create_model_version(session: Session, *, family: str, version_tag: str, source: str | None = None) -> str:
    row = session.execute(
        text("select id from model_versions where family = :family and version_tag = :version_tag"),
        {"family": family, "version_tag": version_tag},
    ).first()
    if row is not None:
        return str(row[0])
    new_id = session.execute(
        text(
            "insert into model_versions (family, version_tag, source) "
            "values (:family, :version_tag, :source) returning id"
        ),
        {"family": family, "version_tag": version_tag, "source": source},
    ).scalar_one()
    session.commit()
    return str(new_id)


def persist_recommendation(
    session: Session,
    *,
    reference_recording_id: str,
    mode: str,
    params: dict,
    model_version_id: str,
    requested_by_user_id: str | None,
) -> str:
    recommendation_id = session.execute(
        text(
            "insert into recommendations "
            "(requested_by_user_id, reference_recording_id, mode, params, model_version_id) "
            "values (:user_id, :reference_id, :mode, :params, :model_version_id) returning id"
        ),
        {
            "user_id": requested_by_user_id,
            "reference_id": reference_recording_id,
            "mode": mode,
            "params": json.dumps(params),
            "model_version_id": model_version_id,
        },
    ).scalar_one()
    session.commit()
    return str(recommendation_id)


def persist_recommendation_results(session: Session, *, recommendation_id: str, scored_candidates: list) -> None:
    for rank, candidate in enumerate(scored_candidates, start=1):
        session.execute(
            text(
                "insert into recommendation_results "
                "(recommendation_id, recording_id, rank, score, dimension_scores, reason_codes) "
                "values (:rec_id, :recording_id, :rank, :score, :dims, :reasons)"
            ),
            {
                "rec_id": recommendation_id,
                "recording_id": candidate.recording_id,
                "rank": rank,
                "score": round(candidate.score, 5),
                "dims": json.dumps(candidate.dimension_scores),
                "reasons": candidate.reason_codes,
            },
        )
    session.commit()


def ensure_app_user(session: Session, *, user_id: str, email: str | None = None) -> None:
    """Our own app_users table mirrors Supabase Auth's user id (see
    005_app_users_and_entitlements.sql) rather than duplicating
    authentication, but nothing creates that mirror row automatically —
    a real Supabase-authenticated user's first write (save a song, run a
    search) would otherwise hit a foreign-key violation on app_users
    that's never been populated. Call this before any write that's
    FK-constrained against app_users, not just from one call site, so a
    forgotten call site elsewhere can't silently reintroduce the bug.
    """
    session.execute(
        text(
            "insert into app_users (id, email) values (:id, :email) "
            "on conflict (id) do nothing"
        ),
        {"id": user_id, "email": email},
    )


def save_song(session: Session, *, user_id: str, recording_id: str) -> None:
    ensure_app_user(session, user_id=user_id)
    session.execute(
        text(
            "insert into saved_songs (user_id, recording_id) values (:user_id, :recording_id) "
            "on conflict (user_id, recording_id) do nothing"
        ),
        {"user_id": user_id, "recording_id": recording_id},
    )
    session.commit()


def unsave_song(session: Session, *, user_id: str, recording_id: str) -> None:
    session.execute(
        text("delete from saved_songs where user_id = :user_id and recording_id = :recording_id"),
        {"user_id": user_id, "recording_id": recording_id},
    )
    session.commit()


def get_saved_songs(session: Session, *, user_id: str, limit: int = 50) -> list[SongDTO]:
    rows = session.execute(
        text(
            "select recording_id from saved_songs where user_id = :user_id "
            "order by saved_at desc limit :limit"
        ),
        {"user_id": user_id, "limit": limit},
    ).all()
    songs = []
    for row in rows:
        song = get_song_dto(session, str(row[0]))
        if song is not None:
            songs.append(song)
    return songs


def record_search(session: Session, *, user_id: str, query_text: str) -> None:
    ensure_app_user(session, user_id=user_id)
    session.execute(
        text("insert into search_history (user_id, query_text) values (:user_id, :query_text)"),
        {"user_id": user_id, "query_text": query_text},
    )
    session.commit()


def get_search_history(session: Session, *, user_id: str, limit: int = 50) -> list[dict]:
    rows = session.execute(
        text(
            "select query_text, created_at from search_history where user_id = :user_id "
            "order by created_at desc limit :limit"
        ),
        {"user_id": user_id, "limit": limit},
    ).mappings().all()
    return [{"query_text": r["query_text"], "created_at": r["created_at"].isoformat()} for r in rows]
