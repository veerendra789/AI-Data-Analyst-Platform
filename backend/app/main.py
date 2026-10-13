import logging

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.api.auth import router as auth_router
from app.api.datasets import router as datasets_router
from app.api.analysis import router as analysis_router
from app.api.reports import router as reports_router
from app.api.data_preparation import router as data_preparation_router
from app.services.supabase_repository import check_database


logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    cors_origins: str = "http://localhost:5173"
    app_env: str = "development"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def validate_production_cors(self) -> "Settings":
        origins = [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
        if self.app_env.lower() in {"production", "prod"} and (
            not origins or "*" in origins or any(not origin.startswith("https://") for origin in origins)
        ):
            raise ValueError("Production CORS_ORIGINS must contain only explicit HTTPS origins.")
        return self


settings = Settings()
app = FastAPI(
    title="AI Data Analyst Platform API",
    version="0.1.0",
    description="Phase 1 service foundation for the AI Data Analyst Platform.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=600,
)

app.include_router(auth_router)
app.include_router(datasets_router)
app.include_router(analysis_router)
app.include_router(reports_router)
app.include_router(data_preparation_router)


def error_code(status_code: int, detail: object) -> str:
    if status_code == 429:
        return "RATE_LIMIT_EXCEEDED"
    if isinstance(detail, str) and detail.endswith("."):
        return detail[:-1].upper().replace(" ", "_").replace("'", "")
    return {400: "BAD_REQUEST", 401: "UNAUTHORIZED", 403: "FORBIDDEN", 404: "NOT_FOUND", 409: "CONFLICT", 413: "PAYLOAD_TOO_LARGE", 422: "VALIDATION_ERROR", 429: "RATE_LIMITED"}.get(status_code, "REQUEST_FAILED")


def error_response(status_code: int, message: str, code: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": {"code": code, "message": message}, "detail": message})


@app.exception_handler(HTTPException)
async def http_error_handler(_: Request, exc: HTTPException) -> JSONResponse:
    message = exc.detail if isinstance(exc.detail, str) else "The request could not be completed."
    return error_response(exc.status_code, message, error_code(exc.status_code, exc.detail))


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, __: RequestValidationError) -> JSONResponse:
    return error_response(422, "The request contains invalid values.", "VALIDATION_ERROR")


@app.exception_handler(Exception)
async def unexpected_error_handler(_: Request, __: Exception) -> JSONResponse:
    logger.exception("Unhandled API exception")
    return error_response(500, "The request could not be completed.", "INTERNAL_ERROR")


@app.get("/", tags=["system"])
@app.get("/health", tags=["system"])
@app.get("/api/index", tags=["system"])
@app.get("/api/index/health", tags=["system"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/health", tags=["system"])
def api_health_check() -> dict[str, str]:
    return {"status": "ok", "service": "api"}


@app.get("/health/db", tags=["system"], response_model=None)
def database_health_check() -> JSONResponse | dict[str, str]:
    try:
        check_database()
        return {"status": "ok", "database": "supabase"}
    except Exception:
        logger.exception("Supabase database health check failed")
        return JSONResponse(status_code=503, content={"status": "error", "database": "unavailable"})
