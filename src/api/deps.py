from fastapi import Header, HTTPException

from src.core.config import settings


async def verify_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    """Exige API key em ambientes não-development."""
    if settings.app_env == "development":
        return
    if not x_api_key or x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="API key inválida ou ausente")
