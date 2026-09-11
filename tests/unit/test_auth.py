"""Tests the real Supabase JWT verification path (app.auth._verify_token)
against a locally generated ES256 keypair — no live Supabase project
needed for this, since what's worth testing is the verification logic
(signature/expiry/audience checks), not PyJWKClient's own HTTP fetch.
`_get_signing_key` is monkeypatched to hand back the local public key
directly instead of fetching a JWKS URL; that's the one seam auth.py
exposes specifically so this doesn't require a network call.

tests/integration/conftest.py sets AUTH_DEV_MODE=true for the rest of the
suite (the X-User-Id placeholder path) — this file exercises the opposite,
non-dev-mode path directly.
"""

import sys
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "api"))

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException

from app import auth
from app.config import settings


@pytest.fixture
def keypair():
    private_key = ec.generate_private_key(ec.SECP256R1())
    return private_key, private_key.public_key()


@pytest.fixture(autouse=True)
def non_dev_mode(monkeypatch):
    monkeypatch.setattr(settings, "auth_dev_mode", False)
    monkeypatch.setattr(settings, "supabase_jwt_audience", "authenticated")


def _sign(private_key, *, sub="user-123", aud="authenticated", exp_delta=3600):
    payload = {"sub": sub, "aud": aud, "exp": int(time.time()) + exp_delta}
    return jwt.encode(payload, private_key, algorithm="ES256")


def _patch_signing_key(monkeypatch, public_key):
    monkeypatch.setattr(auth, "_get_signing_key", lambda token: SimpleNamespace(key=public_key))


async def test_valid_token_returns_sub_claim(keypair, monkeypatch):
    private_key, public_key = keypair
    _patch_signing_key(monkeypatch, public_key)
    token = _sign(private_key, sub="user-abc")

    user_id = await auth.get_current_user_id(authorization=f"Bearer {token}", x_user_id=None)

    assert user_id == "user-abc"


async def test_token_signed_by_a_different_key_is_rejected(keypair, monkeypatch):
    _, public_key = keypair
    other_private_key, _ = (ec.generate_private_key(ec.SECP256R1()), None)
    _patch_signing_key(monkeypatch, public_key)
    forged_token = _sign(other_private_key)

    with pytest.raises(HTTPException) as exc_info:
        await auth.get_current_user_id(authorization=f"Bearer {forged_token}", x_user_id=None)
    assert exc_info.value.status_code == 401


async def test_expired_token_is_rejected(keypair, monkeypatch):
    private_key, public_key = keypair
    _patch_signing_key(monkeypatch, public_key)
    expired_token = _sign(private_key, exp_delta=-60)

    with pytest.raises(HTTPException) as exc_info:
        await auth.get_current_user_id(authorization=f"Bearer {expired_token}", x_user_id=None)
    assert exc_info.value.status_code == 401


async def test_wrong_audience_is_rejected(keypair, monkeypatch):
    private_key, public_key = keypair
    _patch_signing_key(monkeypatch, public_key)
    token = _sign(private_key, aud="some-other-service")

    with pytest.raises(HTTPException) as exc_info:
        await auth.get_current_user_id(authorization=f"Bearer {token}", x_user_id=None)
    assert exc_info.value.status_code == 401


async def test_missing_authorization_header_is_rejected():
    with pytest.raises(HTTPException) as exc_info:
        await auth.get_current_user_id(authorization=None, x_user_id=None)
    assert exc_info.value.status_code == 401


async def test_optional_user_id_returns_none_without_header():
    assert await auth.get_optional_user_id(authorization=None, x_user_id=None) is None


async def test_dev_mode_uses_x_user_id_header_instead(monkeypatch):
    monkeypatch.setattr(settings, "auth_dev_mode", True)

    user_id = await auth.get_current_user_id(authorization=None, x_user_id="dev-user-1")

    assert user_id == "dev-user-1"
