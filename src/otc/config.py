from __future__ import annotations

from decimal import Decimal
from functools import lru_cache
from pathlib import Path

import yaml

from src.otc.models import OtcMartingale, OtcProfileConfig, OtcTelegramConfig

_PROFILE_PATH = Path(__file__).resolve().parent.parent / "profiles" / "otc.yaml"


@lru_cache
def load_otc_config() -> OtcProfileConfig:
    if not _PROFILE_PATH.is_file():
        raise FileNotFoundError(f"Perfil OTC não encontrado: {_PROFILE_PATH}")
    data = yaml.safe_load(_PROFILE_PATH.read_text(encoding="utf-8"))
    otc_raw = data.get("otc") or {}
    mg_raw = otc_raw.get("martingale") or {}
    tg_raw = otc_raw.get("telegram") or {}
    aliases_raw = otc_raw.get("asset_aliases") or {}
    return OtcProfileConfig(
        profile_id=str(data.get("id", "otc")),
        venue=str(otc_raw.get("venue", "iqoption")),
        account_mode=str(otc_raw.get("account_mode", "PRACTICE")).upper(),
        default_stake_usd=Decimal(str(otc_raw.get("default_stake_usd", "5"))),
        max_open_trades=int(otc_raw.get("max_open_trades", 3)),
        expiry_minutes=int(otc_raw.get("expiry_minutes", 1)),
        dry_run=bool(otc_raw.get("dry_run", True)),
        martingale=OtcMartingale(
            enabled=bool(mg_raw.get("enabled", False)),
            max_protections=int(mg_raw.get("max_protections", 0)),
            multiplier=Decimal(str(mg_raw.get("multiplier", "2.0"))),
        ),
        assets=tuple(otc_raw.get("assets") or ()),
        asset_aliases={str(k): str(v) for k, v in aliases_raw.items()},
        telegram=OtcTelegramConfig(
            enabled=bool(tg_raw.get("enabled", False)),
            mode=str(tg_raw.get("mode", "user")).lower(),
            channel=str(tg_raw.get("channel", "")),
        ),
        signal_timezone=str(otc_raw.get("signal_timezone", "America/Sao_Paulo")),
        entry_max_lateness_seconds=int(otc_raw.get("entry_max_lateness_seconds", 0)),
        protection_max_lateness_seconds=int(
            otc_raw.get("protection_max_lateness_seconds", 30)
        ),
    )


def resolve_otc_telegram_chat_id(config: OtcProfileConfig | None = None) -> str:
    from src.core.config import settings

    cfg = config or load_otc_config()
    env_chat = settings.otc_telegram_chat_id.strip()
    if env_chat:
        return env_chat
    return cfg.telegram.channel.strip()


def resolve_iq_asset(symbol: str, config: OtcProfileConfig | None = None) -> str:
    cfg = config or load_otc_config()
    key = symbol.strip()
    if key in cfg.asset_aliases:
        return cfg.asset_aliases[key]
    upper = key.upper()
    if upper in cfg.asset_aliases:
        return cfg.asset_aliases[upper]
    if "(OTC)" in key:
        return key
    return key
