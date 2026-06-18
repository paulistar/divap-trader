from __future__ import annotations

import logging
import time
from decimal import Decimal

from src.core.config import settings
from src.core.exceptions import ExchangeError
from src.otc.config import load_otc_config, resolve_iq_asset
from src.otc.iqoption_client import (
    fetch_iqoption_balance,
    get_iqoption_client,
    iqoption_configured,
    legacy_configured,
    mcp_find_asset_id,
    mcp_pick_instrument,
    otc_transport,
)
from src.otc.mcp_client import fetch_mcp_balance, mcp_call, reset_mcp_client
from src.otc.models import OtcProfileConfig, OtcSignal, OtcTradeResult

logger = logging.getLogger(__name__)

PROFILE_ID = "otc"
MARKET = "binary_otc"
VENUE = "iqoption"


class IqOptionBroker:
    """Execução de opções binárias turbo (M1) na IQ Option via MCP ou iqoptionapi."""

    def __init__(self, config: OtcProfileConfig | None = None) -> None:
        self._config = config or load_otc_config()

    @property
    def configured(self) -> bool:
        return iqoption_configured()

    @property
    def transport(self) -> str | None:
        return otc_transport()

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
                "OTC dry-run: %s %s stake=%s expiry=%sm transport=%s",
                iq_asset,
                signal.direction,
                stake,
                signal.expiry_minutes,
                self.transport,
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

        if self.transport == "mcp":
            return self._place_binary_mcp(signal, iq_asset, stake)
        return self._place_binary_legacy(signal, iq_asset, stake)

    def _place_binary_mcp(
        self,
        signal: OtcSignal,
        iq_asset: str,
        stake: Decimal,
    ) -> OtcTradeResult:
        try:
            _, balance_id = fetch_mcp_balance(self._config.account_mode)
            asset_id, resolved_name = mcp_find_asset_id(iq_asset)
            instrument_id, instrument_index = mcp_pick_instrument(
                asset_id,
                signal.direction,
                signal.expiry_minutes,
            )
            trade_payload = mcp_call(
                "place_trade",
                {
                    "balance_id": balance_id,
                    "instrument_id": instrument_id,
                    "instrument_index": instrument_index,
                    "asset_id": asset_id,
                    "amount": float(stake),
                },
            )
        except ExchangeError as exc:
            return OtcTradeResult(
                executed=False,
                reason=str(exc),
                asset=iq_asset,
                direction=signal.direction,
                stake_usd=stake,
            )

        order_id = str(trade_payload.get("order_id") or "")
        pnl_usd = self._wait_settlement_mcp(
            asset_id=asset_id,
            amount=stake,
            duration_minutes=signal.expiry_minutes,
        )
        return OtcTradeResult(
            executed=True,
            reason="filled",
            order_id=order_id or None,
            asset=resolved_name,
            direction=signal.direction,
            stake_usd=stake,
            pnl_usd=pnl_usd,
            dry_run=False,
        )

    def _place_binary_legacy(
        self,
        signal: OtcSignal,
        iq_asset: str,
        stake: Decimal,
    ) -> OtcTradeResult:
        if not legacy_configured():
            return OtcTradeResult(
                executed=False,
                reason="legacy_credentials_missing",
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

        pnl_usd = self._wait_settlement_legacy(api, order_id, duration)
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

    def _wait_settlement_mcp(
        self,
        asset_id: int,
        amount: Decimal,
        duration_minutes: int,
    ) -> Decimal | None:
        wait_seconds = duration_minutes * 60 + 20
        deadline = time.time() + wait_seconds
        open_position_id: int | None = None

        while time.time() < deadline:
            try:
                positions_payload = mcp_call("list_positions")
            except ExchangeError:
                time.sleep(2)
                continue

            positions = positions_payload.get("positions") or []
            if open_position_id is None:
                for pos in positions:
                    if int(pos.get("asset_id") or 0) != asset_id:
                        continue
                    if Decimal(str(pos.get("amount") or 0)) != amount:
                        continue
                    open_position_id = int(pos["position_id"])
                    break
                time.sleep(2)
                continue

            still_open = any(
                int(pos.get("position_id") or 0) == open_position_id for pos in positions
            )
            if still_open:
                time.sleep(2)
                continue

            history_payload = mcp_call("get_trade_history", {"skip": 0, "limit": 20})
            for row in history_payload.get("history") or []:
                if int(row.get("position_id") or 0) == open_position_id:
                    return Decimal(str(row.get("profit") or 0))
            return None

        return None

    def _wait_settlement_legacy(
        self,
        api: object,
        order_id: object,
        duration_minutes: int,
    ) -> Decimal | None:
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


def reset_broker_connections() -> None:
    reset_mcp_client()
    from src.otc.iqoption_client import reset_iqoption_client

    reset_iqoption_client()
