import hashlib
import hmac
import time
from secrets import compare_digest

from src.core.config import settings

COOKIE_NAME = "divap_dashboard"
SESSION_MAX_AGE = 7 * 24 * 3600


def create_session_token() -> str:
    expires = int(time.time()) + SESSION_MAX_AGE
    payload = f"divap:{expires}"
    signature = hmac.new(
        settings.api_key.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{expires}.{signature}"


def verify_session_token(token: str | None) -> bool:
    if not token:
        return False
    try:
        expires_str, signature = token.split(".", 1)
        expires = int(expires_str)
    except (ValueError, AttributeError):
        return False

    if time.time() > expires:
        return False

    payload = f"divap:{expires}"
    expected = hmac.new(
        settings.api_key.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()
    return compare_digest(signature, expected)


def _safe_compare(left: str, right: str) -> bool:
    if not left or not right:
        return False
    return compare_digest(left, right)


def validate_dashboard_secret(secret: str) -> bool:
    if settings.app_env == "development":
        return True
    if _safe_compare(secret, settings.api_key):
        return True
    if settings.dashboard_token and _safe_compare(secret, settings.dashboard_token):
        return True
    return False
