"""Supabase Auth verification.

Real path: verifies the JWT's signature against the Supabase project's own
JWKS endpoint (`{supabase_url}/auth/v1/.well-known/jwks.json`) using
asymmetric ES256/RS256 — Supabase's current recommended signing scheme.
Supabase's own guidance now advises *against* verifying with the older
HS256 shared-secret approach, so that's deliberately not what's
implemented here. Verification checks signature, expiry, and audience,
then returns the `sub` claim as the user id.

Dev-mode path: an explicit, never-default-on fallback
(`settings.auth_dev_mode`) that accepts a plain `X-User-Id` header instead
— for local development and tests when no live Supabase project is
configured. Same pattern as `spotify_auth_code_enabled` /
`apple_musickit_enabled` elsewhere in this codebase: the real integration
is implemented, but gated until live credentials actually exist. Never
enable this flag in a deployment a real user could reach.
"""

from functools import lru_cache

import jwt
from fastapi import Header, HTTPException
from jwt import PyJWKClient

from app.config import settings


@lru_cache(maxsize=1)
def _jwks_client() -> PyJWKClient:
    if not settings.supabase_url:
        raise RuntimeError("SUPABASE_URL is not configured; cannot verify Supabase Auth JWTs")
    jwks_url = f"{settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
    return PyJWKClient(jwks_url, cache_keys=True)


def _get_signing_key(token: str):
    """Isolated so tests can monkeypatch this one function with a locally
    generated key instead of hitting a live Supabase JWKS endpoint — the
    thing worth testing is the verification logic (signature/expiry/
    audience checks below), not PyJWKClient's own HTTP fetch.
    """
    return _jwks_client().get_signing_key_from_jwt(token)


def _verify_token(token: str) -> str:
    """Returns the verified user id (the `sub` claim). Raises
    HTTPException(401) on any failure — bad signature, expired, wrong
    audience, malformed token, or an unreachable/misconfigured JWKS source.
    A verification failure is always a 401, never a 500: an untrusted
    caller should not learn *why* their token was rejected in more detail
    than "invalid credentials".
    """
    try:
        signing_key = _get_signing_key(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256", "RS256"],
            audience=settings.supabase_jwt_audience,
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="invalid auth token") from exc
    except Exception as exc:
        raise HTTPException(status_code=401, detail="could not verify auth token") from exc

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="auth token missing sub claim")
    return sub


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token


async def get_current_user_id(
    authorization: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
) -> str:
    if settings.auth_dev_mode:
        if not x_user_id:
            raise HTTPException(status_code=401, detail="X-User-Id header required (auth dev mode)")
        return x_user_id

    token = _extract_bearer_token(authorization)
    if token is None:
        raise HTTPException(status_code=401, detail="Authorization: Bearer <token> header required")
    return _verify_token(token)


async def get_optional_user_id(
    authorization: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
) -> str | None:
    if settings.auth_dev_mode:
        return x_user_id

    token = _extract_bearer_token(authorization)
    if token is None:
        return None
    return _verify_token(token)
