from __future__ import annotations

import logging
import time
from decimal import Decimal

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
from src.otc.models import OtcProfileConfig, OtcSettlementContext, OtcSignal, OtcTradeResult

logger = logging.getLogger(__name__)

PROFILE_ID = "otc"
MARKET = "binary_otc"
VENUE = "iqoption"
SETTLEMENT_POLL_FAST_SECONDS = 0.1
SETTLEMENT_POLL_NORMAL_SECONDS = 0.5
SETTLEMENT_AGGRESSIVE_WINDOW_SECONDS = 8
SETTLEMENT_GRACE_AFTER_DEADLINE_SECONDS = 2.0


class IqOptionBroker:
    """Execução de opções binárias turbo (M1) na IQ Option via MCP ou iqoptionapi."""

    def __init__(self, config: OtcProfileConfig | None = None) -> None:
        self._config = config or load_otc_config()
        self._mcp_open_position_ids: dict[str, int] = {}

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
        open_result, settlement_ctx = self.open_binary(signal, stake_usd=stake)
        if not open_result.executed or open_result.dry_run or settlement_ctx is None:
            return open_result
        pnl_usd = self.wait_settlement(settlement_ctx)
        return OtcTradeResult(
            executed=True,
            reason="filled",
            order_id=open_result.order_id,
            asset=open_result.asset,
            direction=open_result.direction,
            stake_usd=open_result.stake_usd,
            pnl_usd=pnl_usd,
            dry_run=False,
        )

    def open_binary(
        self,
        signal: OtcSignal,
        stake_usd: Decimal | None = None,
    ) -> tuple[OtcTradeResult, OtcSettlementContext | None]:
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
            return (
                OtcTradeResult(
                    executed=True,
                    reason="dry_run",
                    asset=iq_asset,
                    direction=signal.direction,
                    stake_usd=stake,
                    dry_run=True,
                ),
                None,
            )

        if not self.configured:
            return (
                OtcTradeResult(
                    executed=False,
                    reason="iqoption_not_configured",
                    asset=iq_asset,
                    direction=signal.direction,
                ),
                None,
            )

        if self.transport == "mcp":
            return self._open_binary_mcp(signal, iq_asset, stake)
        return self._open_binary_legacy(signal, iq_asset, stake)

    def wait_settlement(
        self,
        ctx: OtcSettlementContext,
        *,
        sync_until=None,
        sleep_fn=time.sleep,
        now_fn=None,
    ) -> Decimal | None:
        """Aguarda PnL. Com `sync_until`, sincroniza relógio para martingale no segundo exato."""
        from datetime import datetime

        if now_fn is None:
            tz = sync_until.tzinfo if sync_until is not None else None
            now_fn = lambda: datetime.now(tz) if tz else datetime.now()

        deadline = None
        if sync_until is not None:
            from datetime import timedelta

            deadline = sync_until + timedelta(seconds=SETTLEMENT_GRACE_AFTER_DEADLINE_SECONDS)

        while True:
            pnl = self._poll_settlement_once(ctx)
            now = now_fn()
            if pnl is not None:
                if sync_until is not None and now < sync_until:
                    from src.otc.schedule import sleep_until

                    sleep_until(sync_until, sleep_fn=sleep_fn, now_fn=now_fn)
                return pnl

            if deadline is not None and now >= deadline:
                logger.warning(
                    "OTC settlement timeout após %s (order=%s)",
                    sync_until.strftime("%H:%M:%S") if sync_until else "?",
                    ctx.order_id,
                )
                return None

            interval = SETTLEMENT_POLL_NORMAL_SECONDS
            if sync_until is not None:
                seconds_to_sync = (sync_until - now).total_seconds()
                if seconds_to_sync <= SETTLEMENT_AGGRESSIVE_WINDOW_SECONDS:
                    interval = SETTLEMENT_POLL_FAST_SECONDS
            sleep_fn(interval)

    def _poll_settlement_once(self, ctx: OtcSettlementContext) -> Decimal | None:
        if ctx.transport == "mcp":
            return self._poll_settlement_mcp_once(ctx)
        return self._poll_settlement_legacy_once(ctx)

    def _poll_settlement_mcp_once(self, ctx: OtcSettlementContext) -> Decimal | None:
        if ctx.mcp_asset_id is None:
            return None
        cache_key = ctx.order_id or f"{ctx.mcp_asset_id}:{ctx.stake_usd}"
        try:
            positions_payload = mcp_call("list_positions")
        except ExchangeError:
            return None

        positions = positions_payload.get("positions") or []
        open_position_id = self._find_open_mcp_position_id(ctx, positions)
        if open_position_id is not None:
            self._mcp_open_position_ids[cache_key] = open_position_id
            return None

        position_id = self._mcp_open_position_ids.get(cache_key)
        history_payload = mcp_call("get_trade_history", {"skip": 0, "limit": 20})
        for row in history_payload.get("history") or []:
            if position_id is not None:
                if int(row.get("position_id") or 0) == position_id:
                    self._mcp_open_position_ids.pop(cache_key, None)
                    return Decimal(str(row.get("profit") or 0))
                continue
            if ctx.order_id and str(row.get("order_id") or "") == ctx.order_id:
                return Decimal(str(row.get("profit") or 0))
            if int(row.get("asset_id") or 0) != ctx.mcp_asset_id:
                continue
            if Decimal(str(row.get("amount") or 0)) != ctx.stake_usd:
                continue
            return Decimal(str(row.get("profit") or 0))
        return None

    @staticmethod
    def _find_open_mcp_position_id(
        ctx: OtcSettlementContext,
        positions: list,
    ) -> int | None:
        for pos in positions:
            if ctx.mcp_asset_id and int(pos.get("asset_id") or 0) != ctx.mcp_asset_id:
                continue
            if Decimal(str(pos.get("amount") or 0)) != ctx.stake_usd:
                continue
            return int(pos["position_id"])
        return None

    def _poll_settlement_legacy_once(self, ctx: OtcSettlementContext) -> Decimal | None:
        if ctx.legacy_order_id is None:
            return None
        api = get_iqoption_client()
        try:
            win, profit = api.check_win_v4(ctx.legacy_order_id)
        except Exception:
            return None
        if win is None:
            return None
        return Decimal(str(profit or 0))

    def _open_binary_mcp(
        self,
        signal: OtcSignal,
        iq_asset: str,
        stake: Decimal,
    ) -> tuple[OtcTradeResult, OtcSettlementContext | None]:
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
            return (
                OtcTradeResult(
                    executed=False,
                    reason=str(exc),
                    asset=iq_asset,
                    direction=signal.direction,
                    stake_usd=stake,
                ),
                None,
            )

        order_id = str(trade_payload.get("order_id") or "")
        open_result = OtcTradeResult(
            executed=True,
            reason="opened",
            order_id=order_id or None,
            asset=resolved_name,
            direction=signal.direction,
            stake_usd=stake,
            pnl_usd=None,
            dry_run=False,
        )
        ctx = OtcSettlementContext(
            transport="mcp",
            resolved_asset=resolved_name,
            direction=signal.direction,
            stake_usd=stake,
            duration_minutes=signal.expiry_minutes,
            order_id=order_id or None,
            mcp_asset_id=asset_id,
        )
        return open_result, ctx

    def _open_binary_legacy(
        self,
        signal: OtcSignal,
        iq_asset: str,
        stake: Decimal,
    ) -> tuple[OtcTradeResult, OtcSettlementContext | None]:
        if not legacy_configured():
            return (
                OtcTradeResult(
                    executed=False,
                    reason="legacy_credentials_missing",
                    asset=iq_asset,
                    direction=signal.direction,
                ),
                None,
            )

        api = get_iqoption_client()
        try:
            active_id, resolved_name = self._resolve_active_id(signal.asset)
        except ExchangeError as exc:
            return (
                OtcTradeResult(
                    executed=False,
                    reason=str(exc),
                    asset=iq_asset,
                    direction=signal.direction,
                ),
                None,
            )

        action = "call" if signal.direction == "buy" else "put"
        duration = max(1, signal.expiry_minutes)

        try:
            ok, order_id = api.buy(float(stake), active_id, action, duration)
        except Exception as exc:
            raise ExchangeError(f"IQ Option buy falhou: {exc}") from exc

        if not ok:
            return (
                OtcTradeResult(
                    executed=False,
                    reason=f"order_rejected:{order_id}",
                    asset=resolved_name,
                    direction=signal.direction,
                    stake_usd=stake,
                ),
                None,
            )

        open_result = OtcTradeResult(
            executed=True,
            reason="opened",
            order_id=str(order_id),
            asset=resolved_name,
            direction=signal.direction,
            stake_usd=stake,
            pnl_usd=None,
            dry_run=False,
        )
        ctx = OtcSettlementContext(
            transport="legacy",
            resolved_asset=resolved_name,
            direction=signal.direction,
            stake_usd=stake,
            duration_minutes=duration,
            order_id=str(order_id),
            legacy_order_id=order_id,
        )
        return open_result, ctx


def reset_broker_connections() -> None:
    reset_mcp_client()
    from src.otc.iqoption_client import reset_iqoption_client

    reset_iqoption_client()
