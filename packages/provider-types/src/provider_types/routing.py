from .capabilities import AuthMode
from .errors import ProviderCapabilityError


def select_auth_mode(*, requires_user_data: bool, client_credentials_supported: bool) -> AuthMode:
    """The request routing rule from V2.1 §H, as code instead of prose:

        if operation.requires_user_data:
            require USER_OAUTH
        else:
            prefer CLIENT_CREDENTIALS when supported
            otherwise use an alternative permitted catalog source
        Never: require Spotify user login merely to search or discover music.

    This function only decides the auth *mode* for an operation that some
    provider already supports; it never decides which provider to use.
    Raising rather than silently falling back to USER_OAUTH is deliberate —
    a public catalog/search code path that can't get Client Credentials
    must fall back to a different catalog source (e.g. MusicBrainz), not
    quietly start requiring a user's Spotify login.
    """
    if requires_user_data:
        return AuthMode.USER_OAUTH
    if client_credentials_supported:
        return AuthMode.CLIENT_CREDENTIALS
    raise ProviderCapabilityError(
        provider="<unspecified>",
        operation="anonymous catalog access (no Client Credentials support and operation does not require user data)",
    )
