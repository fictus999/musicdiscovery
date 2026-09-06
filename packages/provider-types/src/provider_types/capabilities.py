from enum import Enum

from pydantic import BaseModel


class AuthMode(str, Enum):
    """How a provider operation authenticates, per V2.1 §G.

    CLIENT_CREDENTIALS: server-to-server, app-only. Cannot access user data.
    Not subject to a per-app user allowlist cap.

    USER_OAUTH: Authorization Code / PKCE, tied to one connected user's
    account. This is the plane capped by Spotify Development Mode's
    five-user allowlist — never route a public catalog operation through
    it (see routing.py).

    NONE: no authentication required (e.g. a public static asset URL).
    """

    CLIENT_CREDENTIALS = "client_credentials"
    USER_OAUTH = "user_oauth"
    NONE = "none"


class ProviderCapabilities(BaseModel):
    """What a given provider adapter instance actually supports right now.

    Declared explicitly rather than assumed (V2 §15): a Spotify adapter in
    Phase 1 Development Mode, for example, sets library_write=False and
    user_playlists=False until Authorization Code is verified and enabled,
    even though the *interface* defines those operations.
    """

    catalog_search: bool = False
    catalog_track_lookup: bool = False
    isrc_lookup: bool = False
    user_profile: bool = False
    user_playlists: bool = False
    playlist_items: bool = False
    library_read: bool = False
    library_write: bool = False
    oauth_user: bool = False
    client_credentials: bool = False
    deep_links: bool = False
    artwork: bool = False
