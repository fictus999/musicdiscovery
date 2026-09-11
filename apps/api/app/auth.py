"""Placeholder current-user resolution.

Reads X-User-Id directly rather than verifying a Supabase Auth JWT. This is
a Phase 1 stand-in so save/history/entitlement routes and their tables are
fully wired and testable now — replace with real Supabase JWT verification
before any deployment a real user could reach; nothing here should be
mistaken for auth.
"""

from fastapi import Header, HTTPException


async def get_current_user_id(x_user_id: str | None = Header(default=None)) -> str:
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-Id header required (placeholder auth)")
    return x_user_id


async def get_optional_user_id(x_user_id: str | None = Header(default=None)) -> str | None:
    return x_user_id
