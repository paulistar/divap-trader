from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import yaml

from src.core.config import settings
from src.profiles.loader import load_profile


@dataclass(frozen=True, slots=True)
class TassoTelegramConfig:
    accept_button_text: str
    detail_button_text: str
    detail_button_index: int


@dataclass(frozen=True, slots=True)
class TassoProfileConfig:
    profile_id: str
    variant: str
    trigger_pattern: str
    telegram: TassoTelegramConfig


def _load_tasso_section(profile_id: str) -> dict | None:
    profile = load_profile(profile_id)
    if profile is None or profile.kind != "tasso":
        return None
    from pathlib import Path

    path = Path(__file__).resolve().parent.parent / "profiles" / f"{profile_id}.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data.get("tasso") if isinstance(data, dict) else None


@lru_cache
def load_tasso_profile_config(profile_id: str) -> TassoProfileConfig | None:
    section = _load_tasso_section(profile_id)
    if not section:
        return None
    tg = section.get("telegram") or {}
    return TassoProfileConfig(
        profile_id=profile_id,
        variant=str(section.get("variant", profile_id)),
        trigger_pattern=str(section.get("trigger_pattern", "")),
        telegram=TassoTelegramConfig(
            accept_button_text=str(tg.get("accept_button_text", "Aceitar")),
            detail_button_text=str(
                tg.get("detail_button_text", "Solicitar detalhes do trade no bot")
            ),
            detail_button_index=int(tg.get("detail_button_index", 1)),
        ),
    )


def tasso_enabled() -> bool:
    return bool(settings.tasso_telegram_enabled)


def financial_move_bot_ref() -> str:
    return settings.tasso_financial_move_bot.strip().lstrip("@")


def configured() -> bool:
    return (
        tasso_enabled()
        and bool(settings.telegram_user_session.strip())
        and settings.telegram_api_id > 0
        and bool(settings.telegram_api_hash.strip())
        and bool(financial_move_bot_ref())
    )
