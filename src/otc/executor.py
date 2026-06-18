from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal

from src.core.config import settings
from src.data.repositories.trade_repo import TradeRepository
from src.otc.broker import IqOptionBroker, MARKET, PROFILE_ID, VENUE
from src.otc.config import load_otc_config
from src.otc.models import OtcSignal, OtcTradeResult

logger = logging.getLogger(__name__)


class OtcExecutor:
    """Executa sinais OTC sem passar pelo gate/scanner DIVAP."""

    def __init__(
        self,
        broker: IqOptionBroker | None = None,
        trade_repo: TradeRepository | None = None,
    ) -> None:
        self._config = load_otc_config()
        self._broker = broker or IqOptionBroker(self._config)
        self._repo = trade_repo or TradeRepository()

    def try_execute(self, signal: OtcSignal) -> OtcTradeResult:
        if not settings.otc_trading_enabled and not self._config.dry_run:
            return OtcTradeResult(
                executed=False,
                reason="otc_trading_disabled",
                asset=signal.asset,
                direction=signal.direction,
            )

        open_count = self._repo.count_open_trades(PROFILE_ID)
        if open_count >= self._config.max_open_trades:
            return OtcTradeResult(
                executed=False,
                reason="max_open_trades",
                asset=signal.asset,
                direction=signal.direction,
            )

        stake = self._stake_for_signal(signal)
        result = self._broker.place_binary(signal, stake_usd=stake)
        if not result.executed:
            return result

        trade_id = self._persist_trade(signal, result)
        return OtcTradeResult(
            executed=True,
            reason=result.reason,
            trade_id=trade_id,
            order_id=result.order_id,
            asset=result.asset,
            direction=result.direction,
            stake_usd=result.stake_usd,
            pnl_usd=result.pnl_usd,
            dry_run=result.dry_run,
        )

    def _stake_for_signal(self, signal: OtcSignal) -> Decimal:
        base = self._config.default_stake_usd
        if not self._config.martingale.enabled or signal.protection_level <= 0:
            return base
        level = min(signal.protection_level, self._config.martingale.max_protections)
        multiplier = self._config.martingale.multiplier ** level
        return (base * multiplier).quantize(Decimal("0.01"))

    def _persist_trade(self, signal: OtcSignal, result: OtcTradeResult) -> int | None:
        if result.dry_run:
            return None

        now = datetime.now(UTC)
        status = "closed" if result.pnl_usd is not None else "open"
        pnl = result.pnl_usd
        trade_id = self._repo.create_trade(
            alert_id=None,
            symbol=result.asset,
            timeframe=f"{signal.expiry_minutes}m",
            direction=signal.direction,
            confidence="medium",
            status=status,
            entry_price=Decimal("0"),
            stop_loss=Decimal("0"),
            take_profit=Decimal("0"),
            quantity=result.stake_usd,
            quote_amount=result.stake_usd,
            context_verdict=None,
            context_score=None,
            exchange_order_id=result.order_id,
            stop_order_id=None,
            tp_order_id=None,
            trading_mode=self._config.account_mode.lower(),
            opened_at=now,
            profile_id=PROFILE_ID,
            goal_protected=False,
            market=MARKET,
            venue=VENUE,
        )
        if status == "closed" and pnl is not None and trade_id:
            exit_price = Decimal("0")
            pnl_pct = (
                (pnl / result.stake_usd * Decimal("100"))
                if result.stake_usd > 0
                else Decimal("0")
            )
            self._repo.close_trade(
                trade_id=trade_id,
                exit_price=exit_price,
                pnl_usdt=pnl,
                pnl_pct=pnl_pct,
                close_reason="expiry",
                closed_at=now,
            )
        return trade_id
