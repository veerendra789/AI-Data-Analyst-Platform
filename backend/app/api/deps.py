from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.supabase import InvalidAccessToken, SupabaseUnavailable, verify_access_token
from app.services.supabase_repository import create_or_update_user


bearer_scheme = HTTPBearer(auto_error=False)


def bearer_token(credentials: HTTPAuthorizationCredentials | None) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> object:
    token = bearer_token(credentials)
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        auth_user = verify_access_token(token)
    except InvalidAccessToken:
        raise credentials_error from None
    except SupabaseUnavailable:
        raise HTTPException(status_code=503, detail="Authentication service is unavailable.") from None

    user = create_or_update_user(auth_user.uid, auth_user.email, auth_user.name)
    if not user.is_active:
        raise credentials_error
    return user


def get_supabase_identity(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> object:
    token = bearer_token(credentials)
    try:
        return verify_access_token(token)
    except InvalidAccessToken:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    except SupabaseUnavailable:
        raise HTTPException(status_code=503, detail="Authentication service is unavailable.") from None


def require_roles(*roles: str) -> Callable:
    def role_dependency(current_user: object = Depends(get_current_user)) -> object:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource.",
            )
        return current_user

    return role_dependency
