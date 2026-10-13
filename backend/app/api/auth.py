from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_roles
from app.schemas.auth import UserResponse
from app.services.supabase_repository import create_or_update_user


router = APIRouter(prefix="/api/auth", tags=["Authentication"])


class ProfileSyncRequest(BaseModel):
    displayName: str = Field(default="Analyst", min_length=1, max_length=120)


def response_for(user: object) -> UserResponse:
    return UserResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,
        created_at=user.created_at,
    )


@router.post("/profile", response_model=UserResponse)
def sync_profile(
    payload: ProfileSyncRequest,
    current_user: object = Depends(get_current_user),
) -> UserResponse:
    user = create_or_update_user(current_user.uid, current_user.email.lower(), payload.displayName.strip())
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account is inactive.")
    return response_for(user)


@router.get("/me", response_model=UserResponse)
def get_me(current_user: object = Depends(get_current_user)) -> UserResponse:
    return response_for(current_user)


@router.get("/admin-check")
def admin_check(current_user: object = Depends(require_roles("ADMIN"))) -> dict[str, str]:
    return {"status": "ok", "role": str(current_user.role)}
