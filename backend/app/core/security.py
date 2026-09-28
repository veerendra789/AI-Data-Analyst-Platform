from datetime import datetime, timedelta, timezone
import secrets

import jwt
from pwdlib import PasswordHash
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


password_hash = PasswordHash.recommended()
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60


class SecuritySettings(BaseSettings):
    app_env: str = "development"
    jwt_secret: str = secrets.token_urlsafe(32)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def validate_production_secret(self) -> "SecuritySettings":
        if self.app_env.lower() in {"production", "prod"} and (
            len(self.jwt_secret) < 32 or self.jwt_secret == "replace-with-a-long-random-secret"
        ):
            raise ValueError("JWT_SECRET must be a unique secret with at least 32 characters in production.")
        return self


settings = SecuritySettings()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def create_access_token(subject: str, role: str, secret_key: str) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": subject, "role": role, "exp": expires_at}
    return jwt.encode(payload, secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str, secret_key: str) -> dict[str, object]:
    return jwt.decode(token, secret_key, algorithms=[ALGORITHM])
