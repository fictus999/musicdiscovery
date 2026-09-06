from fastapi.testclient import TestClient
from sqlalchemy import text

from app.catalog.normalize import normalize_artist, normalize_title
from app.db.session import get_session
from app.main import app


def _get_or_create_artist(session, artist_name: str) -> str:
    """Real ingestion dedupes artists by mbid, not name (two different real
    artists can share a name) — but this test fixture only ever seeds one
    fictional 'Frank Ocean', so look up by normalized name to avoid
    creating a second, unrelated artist row on every call.
    """
    existing = session.execute(
        text("select id from artist where normalized_name = :norm"),
        {"norm": normalize_artist(artist_name)},
    ).first()
    if existing is not None:
        return str(existing[0])
    return str(
        session.execute(
            text("insert into artist (name, normalized_name) values (:name, :norm) returning id"),
            {"name": artist_name, "norm": normalize_artist(artist_name)},
        ).scalar_one()
    )


def _seed_recording(session, *, title: str, artist_name: str, length_ms: int, release_year: int | None = None):
    artist_id = _get_or_create_artist(session, artist_name)
    recording_id = session.execute(
        text(
            "insert into recording (title, normalized_title, length_ms) "
            "values (:title, :norm, :length_ms) returning id"
        ),
        {"title": title, "norm": normalize_title(title), "length_ms": length_ms},
    ).scalar_one()
    session.execute(
        text("insert into recording_artists (recording_id, artist_id, credit_order) values (:rid, :aid, 0)"),
        {"rid": recording_id, "aid": artist_id},
    )
    if release_year is not None:
        release_group_id = session.execute(
            text(
                "insert into release_group (title, normalized_title) values (:title, :norm) returning id"
            ),
            {"title": title, "norm": normalize_title(title)},
        ).scalar_one()
        release_id = session.execute(
            text(
                "insert into release (release_group_id, title, normalized_title, release_date) "
                "values (:rgid, :title, :norm, :date) returning id"
            ),
            {"rgid": release_group_id, "title": title, "norm": normalize_title(title), "date": f"{release_year}-01-01"},
        ).scalar_one()
        session.execute(
            text(
                "insert into release_recordings (release_id, recording_id, medium_number, track_position) "
                "values (:release_id, :recording_id, 1, 1)"
            ),
            {"release_id": release_id, "recording_id": recording_id},
        )
    session.commit()
    return str(recording_id), str(artist_id)


def test_full_search_and_recommendation_flow(engine, db_session):
    app.dependency_overrides[get_session] = lambda: db_session
    try:
        client = TestClient(app)

        assert client.get("/health").json() == {"status": "ok"}

        ref_id, artist_id = _seed_recording(
            db_session, title="Nights", artist_name="Frank Ocean", length_ms=307000, release_year=2016
        )
        same_artist_id, _ = _seed_recording(
            db_session, title="Solo", artist_name="Frank Ocean", length_ms=257000, release_year=2016
        )

        search_resp = client.get("/music/search", params={"q": "nights"})
        assert search_resp.status_code == 200
        assert any(s["recording_id"] == ref_id for s in search_resp.json()["results"])

        rec_resp = client.post("/recommendations", json={"track_id": ref_id, "mode": "overall", "limit": 10})
        assert rec_resp.status_code == 200
        body = rec_resp.json()
        assert body["reference"]["recording_id"] == ref_id
        assert any(r["song"]["recording_id"] == same_artist_id for r in body["results"])
        assert "SAME_ARTIST" in body["results"][0]["reason_codes"]

        # GET /recommendations/:id round-trips what POST just persisted.
        rec_id = db_session.execute(
            text("select id from recommendations where reference_recording_id = :ref order by created_at desc limit 1"),
            {"ref": ref_id},
        ).scalar_one()
        get_resp = client.get(f"/recommendations/{rec_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["model_version"] == "baseline-v1"

        user_id = db_session.execute(
            text("insert into app_users (id, email) values (gen_random_uuid(), 'test@example.com') returning id")
        ).scalar_one()
        db_session.commit()

        save_resp = client.post(f"/songs/{ref_id}/save", headers={"X-User-Id": str(user_id)})
        assert save_resp.status_code == 200

        unauthenticated = client.post(f"/songs/{ref_id}/save")
        assert unauthenticated.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_recommendation_for_unknown_track_is_404(engine, db_session):
    app.dependency_overrides[get_session] = lambda: db_session
    try:
        client = TestClient(app)
        resp = client.post(
            "/recommendations",
            json={"track_id": "00000000-0000-0000-0000-000000000000", "mode": "overall", "limit": 10},
        )
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.clear()
