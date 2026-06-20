from __future__ import annotations

from src.core.config import settings


def invezt_enabled() -> bool:
    return bool(settings.invezt_telegram_enabled)


def chat_ref() -> str:
    return settings.invezt_telegram_chat_ref.strip()


def configured() -> bool:
    return (
        invezt_enabled()
        and settings.telegram_api_id > 0
        and bool(settings.telegram_api_hash.strip())
        and bool(settings.telegram_user_session.strip())
    )
