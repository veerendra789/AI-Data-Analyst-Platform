from __future__ import annotations

import logging
import os
from functools import lru_cache
from types import SimpleNamespace
from urllib.parse import urlparse

from supabase import Client, ClientOptions, create_client
from supabase_auth.errors import AuthApiError, AuthInvalidJwtError


EXPECTED_PROJECT_REF = "azfaieuwnhgjbedfeybl"
logger = logging.getLogger(__name__)


class InvalidAccessToken(Exception):
    pass


class SupabaseUnavailable(Exception):
    pass


@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    secret_key = os.getenv("SUPABASE_SECRET_KEY", "").strip()
    if not url or not secret_key:
        raise SupabaseUnavailable("Supabase server configuration is incomplete.")
    if urlparse(url).hostname != f"{EXPECTED_PROJECT_REF}.supabase.co":
        raise SupabaseUnavailable(f"SUPABASE_URL must target project {EXPECTED_PROJECT_REF}.")
    return create_client(
        url,
        secret_key,
        options=ClientOptions(auto_refresh_token=False, persist_session=False),
    )


def verify_access_token(token: str) -> SimpleNamespace:
    try:
        response = get_supabase_client().auth.get_user(token)
    except (AuthInvalidJwtError, ValueError) as exc:
        raise InvalidAccessToken from exc
    except AuthApiError as exc:
        if getattr(exc, "status", None) in {400, 401, 403}:
            raise InvalidAccessToken from exc
        logger.exception("Supabase Auth token verification failed")
        raise SupabaseUnavailable from exc
    except Exception as exc:
        logger.exception("Supabase Auth is unavailable")
        raise SupabaseUnavailable from exc

    user = getattr(response, "user", None)
    if user is None or not getattr(user, "id", None):
        raise InvalidAccessToken
    metadata = getattr(user, "user_metadata", None) or {}
    return SimpleNamespace(
        id=str(user.id),
        uid=str(user.id),
        email=getattr(user, "email", None) or "",
        name=metadata.get("display_name") or metadata.get("full_name") or "Analyst",
        auth_user=user,
    )