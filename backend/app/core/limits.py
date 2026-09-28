from collections.abc import Callable

from fastapi import Depends, HTTPException, status

from app.api.deps import get_current_user
from app.core.redis import increment_with_expiry
from app.models import User


def rate_limit(scope: str, limit: int = 30, window_seconds: int = 60) -> Callable:
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        count = increment_with_expiry(f"rate:{scope}:{current_user.id}", window_seconds)
        if count > limit:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded. Please try again later.")
        return current_user

    return dependency
