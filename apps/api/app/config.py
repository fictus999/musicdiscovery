from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/musicdiscovery"

    spotify_client_id: str = ""
    spotify_client_secret: str = ""
    spotify_auth_code_enabled: bool = False

    apple_musickit_enabled: bool = False

    # Real auth is JWKS-verified Supabase Auth JWTs (app/auth.py) — Supabase's
    # own current guidance prefers asymmetric ES256/RS256 verified against
    # the project's JWKS endpoint over the legacy HS256 shared-secret
    # approach, so that's what's implemented here, not the older scheme.
    # auth_dev_mode is an explicit, never-default-on escape hatch for local
    # development and tests when no live Supabase project is configured —
    # mirrors spotify_auth_code_enabled/apple_musickit_enabled: real
    # integration code exists, gated until live credentials exist.
    supabase_url: str = ""
    supabase_jwt_audience: str = "authenticated"
    auth_dev_mode: bool = False

    musicbrainz_user_agent: str = "music-discovery/0.1.0"
    cover_art_archive_base_url: str = "https://coverartarchive.org"

    cors_allowed_origins: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]


settings = Settings()
