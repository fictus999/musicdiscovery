from pydantic import BaseModel


class ProviderLink(BaseModel):
    provider: str
    status: str  # ProviderLinkStatus value, kept as str here to avoid a hard dep on provider_types
    url: str | None = None


class SongDTO(BaseModel):
    """The canonical song shape returned to the frontend. Never a provider
    object (V2.2 §11 acceptance criteria) — recording_id is our own uuid.
    """

    recording_id: str
    title: str
    artist_names: list[str]
    album_title: str | None = None
    length_ms: int | None = None
    artwork_url: str | None = None
    provider_links: list[ProviderLink] = []
