from __future__ import annotations

import logging
import time
from decimal import Decimal

from src.core.exceptions import ExchangeError
from src.otc.config import load_otc_config, resolve_iq_asset
from src.otc.iqoption_client import fetch_iqoption_balance, get_iqoption_client, iqoption_configured
from src.otc.models import OtcProfileConfig, OtcSignal, OtcTradeResult

logger = logging.getLogger(__name__)

PROFILE_ID = "otc"
MARKET = "binary_otc"
VENUE = "iqoption"


class IqOptionBroker:
    """Execução de opções binárias turbo (M1) na IQ Option."""

    def __init__(self, config: OtcProfileConfig | None = None) -> None:
        self._config = config or load_otc_config()

    @property
    def configured(self) -> bool:
        return iqoption_configured()

    def get_balance_usd(self) -> Decimal:
        return fetch_iqoption_balance()

    def _resolve_active_id(self, asset: str) -> tuple[int, str]:
        api = get_iqoption_client()
        iq_name = resolve_iq_asset(asset, self._config)
        all_actives = api.get_all_open_time()
        turbo = all_actives.get("turbo") or {}
        binary = all_actives.get("binary") or {}
        merged = {**binary, **turbo}

        for active_id, meta in merged.items():
            if not isinstance(meta, dict):
                continue
            name = str(meta.get("name") or "")
            if name.lower() == iq_name.lower() and meta.get("open"):
                return int(active_id), name

        for active_id, meta in merged.items():
            if not isinstance(meta, dict):
                continue
            name = str(meta.get("name") or "")
            if iq_name.lower() in name.lower() and meta.get("open"):
                return int(active_id), name

        raise ExchangeError(f"Ativo OTC indisponível na IQ Option: {iq_name}")

    def place_binary(self, signal: OtcSignal, stake_usd: Decimal | None = None) -> OtcTradeResult:
        stake = stake_usd or self._config.default_stake_usd
        iq_asset = resolve_iq_asset(signal.asset, self._config)

        if self._config.dry_run:
            logger.info(
                "OTC dry-run: %s %s stake=%s expiry=%sm",
                iq_asset,
                signal.direction,
                stake,
                signal.expiry_minutes,
            )
            return OtcTradeResult(
                executed=True,
                reason="dry_run",
                asset=iq_asset,
                direction=signal.direction,
                stake_usd=stake,
                dry_run=True,
            )

        if not self.configured:
            return OtcTradeResult(
                executed=False,
                reason="iqoption_not_configured",
                asset=iq_asset,
                direction=signal.direction,
            )

        api = get_iqoption_client()
        try:
            active_id, resolved_name = self._resolve_active_id(signal.asset)
        except ExchangeError as exc:
            return OtcTradeResult(
                executed=False,
                reason=str(exc),
                asset=iq_asset,
                direction=signal.direction,
            )

        action = "call" if signal.direction == "buy" else "put"
        duration = max(1, signal.expiry_minutes)

        try:
            ok, order_id = api.buy(float(stake), active_id, action, duration)
        except Exception as exc:
            raise ExchangeError(f"IQ Option buy falhou: {exc}") from exc

        if not ok:
            return OtcTradeResult(
                executed=False,
                reason=f"order_rejected:{order_id}",
                asset=resolved_name,
                direction=signal.direction,
                stake_usd=stake,
            )

        pnl_usd = self._wait_settlement(api, order_id, duration)
        return OtcTradeResult(
            executed=True,
            reason="filled",
            order_id=str(order_id),
            asset=resolved_name,
            direction=signal.direction,
            stake_usd=stake,
            pnl_usd=pnl_usd,
            dry_run=False,
        )

    def _wait_settlement(self, api: object, order_id: object, duration_minutes: int) -> Decimal | None:
        wait_seconds = duration_minutes * 60 + 15
        deadline = time.time() + wait_seconds
        while time.time() < deadline:
            try:
                win, profit = api.check_win_v4(order_id)
            except Exception:
                time.sleep(2)
                continue
            if win is not None:
                return Decimal(str(profit or 0))
            time.sleep(2)
        return None
