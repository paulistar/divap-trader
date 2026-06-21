"""Configuração runtime do perfil OTC (IQ Option).

Tabela de linha única (id = 1) que sobrepõe o ``otc.yaml`` para os campos
ajustáveis pelo painel: valor das entradas (stake), banca inicial de
referência, metas (diária/mensal), travas de stop e taxa US$→R$.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import psycopg2
from psycopg2.extras import RealDictCursor

SELECT_OTC_SETTINGS_SQL = "SELECT * FROM otc_settings WHERE id = 1"

UPSERT_OTC_SETTINGS_SQL = """
INSERT INTO otc_settings (
    id, stake_usd, initial_bankroll_usd, daily_goal_usd, monthly_goal_usd,
    daily_stop_loss_pct, daily_stop_win_pct, stop_win_enabled, stop_loss_enabled, usd_brl_rate,
    stake_pct, stake_min_usd, stake_max_usd, stake_risk_profile
) VALUES (1, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (id) DO UPDATE SET
    stake_usd = EXCLUDED.stake_usd,
    initial_bankroll_usd = EXCLUDED.initial_bankroll_usd,
    daily_goal_usd = EXCLUDED.daily_goal_usd,
    monthly_goal_usd = EXCLUDED.monthly_goal_usd,
    daily_stop_loss_pct = EXCLUDED.daily_stop_loss_pct,
    daily_stop_win_pct = EXCLUDED.daily_stop_win_pct,
    stop_win_enabled = EXCLUDED.stop_win_enabled,
    stop_loss_enabled = EXCLUDED.stop_loss_enabled,
    usd_brl_rate = EXCLUDED.usd_brl_rate,
    stake_pct = EXCLUDED.stake_pct,
    stake_min_usd = EXCLUDED.stake_min_usd,
    stake_max_usd = EXCLUDED.stake_max_usd,
    stake_risk_profile = EXCLUDED.stake_risk_profile,
    updated_at = NOW()
RETURNING *
"""


def _dec(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    return Decimal(str(value))


@dataclass(frozen=True, slots=True)
class OtcSettingsRecord:
    stake_usd: Decimal | None
    initial_bankroll_usd: Decimal | None
    daily_goal_usd: Decimal | None
    monthly_goal_usd: Decimal | None
    daily_stop_loss_pct: Decimal | None
    daily_stop_win_pct: Decimal | None
    stop_win_enabled: bool
    stop_loss_enabled: bool
    usd_brl_rate: Decimal | None
    stake_pct: Decimal | None
    stake_min_usd: Decimal | None
    stake_max_usd: Decimal | None
    stake_risk_profile: str

    def to_dict(self) -> dict:
        def s(value: Decimal | None) -> str | None:
            return str(value) if value is not None else None

        return {
            "stake_usd": s(self.stake_usd),
            "initial_bankroll_usd": s(self.initial_bankroll_usd),
            "daily_goal_usd": s(self.daily_goal_usd),
            "monthly_goal_usd": s(self.monthly_goal_usd),
            "daily_stop_loss_pct": s(self.daily_stop_loss_pct),
            "daily_stop_win_pct": s(self.daily_stop_win_pct),
            "stop_win_enabled": self.stop_win_enabled,
            "stop_loss_enabled": self.stop_loss_enabled,
            "usd_brl_rate": s(self.usd_brl_rate),
            "stake_pct": s(self.stake_pct),
            "stake_min_usd": s(self.stake_min_usd),
            "stake_max_usd": s(self.stake_max_usd),
            "stake_risk_profile": self.stake_risk_profile,
        }


_EMPTY = OtcSettingsRecord(
    stake_usd=None,
    initial_bankroll_usd=None,
    daily_goal_usd=None,
    monthly_goal_usd=None,
    daily_stop_loss_pct=None,
    daily_stop_win_pct=None,
    stop_win_enabled=False,
    stop_loss_enabled=False,
    usd_brl_rate=None,
    stake_pct=None,
    stake_min_usd=Decimal("1.00"),
    stake_max_usd=None,
    stake_risk_profile="moderate",
)


class OtcSettingsRepository:
    def __init__(self, database_url: str | None = None) -> None:
        from src.core.config import settings

        self._database_url = database_url or settings.database_url

    def _connection(self):
        return psycopg2.connect(self._database_url)

    def get_settings(self) -> OtcSettingsRecord:
        with self._connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(SELECT_OTC_SETTINGS_SQL)
                row = cur.fetchone()
        if row is None:
            return _EMPTY
        return self._row_to_record(row)

    def update_settings(self, **fields: object) -> OtcSettingsRecord:
        current = self.get_settings()
        merged = {
            "stake_usd": current.stake_usd,
            "initial_bankroll_usd": current.initial_bankroll_usd,
            "daily_goal_usd": current.daily_goal_usd,
            "monthly_goal_usd": current.monthly_goal_usd,
            "daily_stop_loss_pct": current.daily_stop_loss_pct,
            "daily_stop_win_pct": current.daily_stop_win_pct,
            "stop_win_enabled": current.stop_win_enabled,
            "stop_loss_enabled": current.stop_loss_enabled,
            "usd_brl_rate": current.usd_brl_rate,
            "stake_pct": current.stake_pct,
            "stake_min_usd": current.stake_min_usd,
            "stake_max_usd": current.stake_max_usd,
            "stake_risk_profile": current.stake_risk_profile,
        }
        for key in ("stop_win_enabled", "stop_loss_enabled"):
            if key in fields and fields[key] is not None:
                merged[key] = bool(fields[key])
        if "stake_risk_profile" in fields and fields["stake_risk_profile"] is not None:
            merged["stake_risk_profile"] = str(fields["stake_risk_profile"]).strip().lower()
        for key in (
            "stake_usd",
            "initial_bankroll_usd",
            "daily_goal_usd",
            "monthly_goal_usd",
            "daily_stop_loss_pct",
            "daily_stop_win_pct",
            "usd_brl_rate",
            "stake_pct",
            "stake_min_usd",
            "stake_max_usd",
        ):
            if key in fields:
                merged[key] = _dec(fields[key])

        with self._connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    UPSERT_OTC_SETTINGS_SQL,
                    (
                        merged["stake_usd"],
                        merged["initial_bankroll_usd"],
                        merged["daily_goal_usd"],
                        merged["monthly_goal_usd"],
                        merged["daily_stop_loss_pct"],
                        merged["daily_stop_win_pct"],
                        merged["stop_win_enabled"],
                        merged["stop_loss_enabled"],
                        merged["usd_brl_rate"],
                        merged["stake_pct"],
                        merged["stake_min_usd"],
                        merged["stake_max_usd"],
                        merged["stake_risk_profile"],
                    ),
                )
                row = cur.fetchone()
        return self._row_to_record(row)

    def _row_to_record(self, row: dict) -> OtcSettingsRecord:
        return OtcSettingsRecord(
            stake_usd=_dec(row.get("stake_usd")),
            initial_bankroll_usd=_dec(row.get("initial_bankroll_usd")),
            daily_goal_usd=_dec(row.get("daily_goal_usd")),
            monthly_goal_usd=_dec(row.get("monthly_goal_usd")),
            daily_stop_loss_pct=_dec(row.get("daily_stop_loss_pct")),
            daily_stop_win_pct=_dec(row.get("daily_stop_win_pct")),
            stop_win_enabled=bool(row.get("stop_win_enabled", False)),
            stop_loss_enabled=bool(row.get("stop_loss_enabled", False)),
            usd_brl_rate=_dec(row.get("usd_brl_rate")),
            stake_pct=_dec(row.get("stake_pct")),
            stake_min_usd=_dec(row.get("stake_min_usd")),
            stake_max_usd=_dec(row.get("stake_max_usd")),
            stake_risk_profile=str(row.get("stake_risk_profile") or "moderate"),
        )
