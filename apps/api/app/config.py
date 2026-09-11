from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/musicdiscovery"

    spotify_client_id: str = ""
    spotify_client_secret: str = ""
    spotify_auth_code_enabled: bool = False

    apple_musickit_enabled: bool = False

    musicbrainz_user_agent: str = "music-discovery/0.1.0"
    cover_art_archive_base_url: str = "https://coverartarchive.org"

    cors_allowed_origins: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]


settings = Settings()
