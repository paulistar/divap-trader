from __future__ import annotations

import logging
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

from src.core.config import settings
from src.data.repositories.otc_settings_repo import OtcSettingsRepository
from src.data.repositories.trade_repo import TradeRepository
from src.otc.broker import IqOptionBroker, MARKET, PROFILE_ID, VENUE
from src.otc.config import load_otc_config
from src.otc.guard import evaluate_otc_stop
from src.otc.martingale import (
    is_loss,
    is_win,
    max_auto_protections_for_signal,
    sequence_reason,
    stake_for_level,
)
from src.otc.models import OtcSequenceResult, OtcSignal, OtcTradeResult
from src.otc.schedule import has_scheduled_legs, resolve_leg_datetime, wait_for_leg

logger = logging.getLogger(__name__)


class OtcExecutor:
    """Executa sinais OTC sem passar pelo gate/scanner DIVAP."""

    def __init__(
        self,
        broker: IqOptionBroker | None = None,
        trade_repo: TradeRepository | None = None,
        settings_repo: OtcSettingsRepository | None = None,
    ) -> None:
        self._config = load_otc_config()
        self._broker = broker or IqOptionBroker(self._config)
        self._repo = trade_repo or TradeRepository()
        self._settings_repo = settings_repo or OtcSettingsRepository()

    def try_execute(self, signal: OtcSignal) -> OtcSequenceResult:
        if not settings.otc_trading_enabled and not self._config.dry_run:
            return self._sequence_result(
                signal,
                (
                    OtcTradeResult(
                        executed=False,
                        reason="otc_trading_disabled",
                        asset=signal.asset,
                        direction=signal.direction,
                    ),
                ),
            )

        stop_reason = evaluate_otc_stop(
            trade_repo=self._repo,
            settings_repo=self._settings_repo,
            timezone=self._config.signal_timezone,
        )
        if stop_reason:
            return self._sequence_result(
                signal,
                (
                    OtcTradeResult(
                        executed=False,
                        reason=stop_reason,
                        asset=signal.asset,
                        direction=signal.direction,
                    ),
                ),
            )

        open_count = self._repo.count_open_trades(PROFILE_ID)
        if open_count >= self._config.max_open_trades:
            return self._sequence_result(
                signal,
                (
                    OtcTradeResult(
                        executed=False,
                        reason="max_open_trades",
                        asset=signal.asset,
                        direction=signal.direction,
                    ),
                ),
            )

        max_protections = max_auto_protections_for_signal(signal, self._config.martingale)
        start_level = max(0, signal.protection_level)
        legs: list[OtcTradeResult] = []

        for level in range(start_level, max_protections + 1):
            leg_signal = replace(signal, protection_level=level)
            leg_result = self._execute_leg(leg_signal, level, max_protections)
            legs.append(leg_result)

            if not leg_result.executed:
                logger.warning(
                    "OTC sequência interrompida nível %s (%s %s stake=%s): %s",
                    level,
                    signal.asset,
                    signal.direction,
                    leg_result.stake_usd,
                    leg_result.reason,
                )
                break
            if leg_result.dry_run:
                break
            if leg_result.pnl_usd is None:
                logger.warning(
                    "OTC leg %s sem PnL após settlement (order=%s, %s %s stake=%s) "
                    "— interrompe sequência martingale",
                    level,
                    leg_result.order_id,
                    signal.asset,
                    signal.direction,
                    leg_result.stake_usd,
                )
                break
            if is_win(leg_result):
                logger.info("OTC sequência venceu na proteção nível %s", level)
                break
            if is_loss(leg_result) and level < max_protections:
                logger.info(
                    "OTC loss nível %s — próxima proteção %s",
                    level,
                    level + 1,
                )
                continue
            break

        from src.otc.stop_alert import check_and_notify_otc_stop

        if any(leg.executed and not leg.dry_run for leg in legs):
            check_and_notify_otc_stop(
                trade_repo=self._repo,
                settings_repo=self._settings_repo,
                timezone=self._config.signal_timezone,
            )

        return self._sequence_result(signal, tuple(legs), max_protections)

    def _execute_leg(
        self,
        signal: OtcSignal,
        level: int,
        max_protections: int,
    ) -> OtcTradeResult:
        use_schedule = has_scheduled_legs(signal)

        if use_schedule:
            max_lateness = (
                self._config.entry_max_lateness_seconds
                if level == 0
                else self._config.protection_max_lateness_seconds
            )
            ok, skip_reason = wait_for_leg(
                signal,
                level,
                self._config.signal_timezone,
                max_lateness_seconds=max_lateness,
            )
            if not ok:
                return OtcTradeResult(
                    executed=False,
                    reason=skip_reason or "scheduled_time_missed",
                    asset=signal.asset,
                    direction=signal.direction,
                    protection_level=level,
                )

        stake = stake_for_level(
            self._effective_base_stake(),
            self._config.martingale,
            level,
        )

        if use_schedule and not self._config.dry_run:
            return self._execute_leg_timed(signal, level, max_protections, stake)

        result = self._broker.place_binary(signal, stake_usd=stake)
        if not result.executed:
            return replace(result, protection_level=level)

        trade_id = self._persist_trade(signal, result, level)
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
            protection_level=level,
        )

    def _execute_leg_timed(
        self,
        signal: OtcSignal,
        level: int,
        max_protections: int,
        stake: Decimal,
    ) -> OtcTradeResult:
        open_result, settlement_ctx = self._broker.open_binary(signal, stake_usd=stake)
        if not open_result.executed:
            return replace(open_result, protection_level=level)
        if settlement_ctx is None:
            return replace(open_result, protection_level=level)

        has_next = level < max_protections
        sync_until = None
        if has_next:
            sync_until = resolve_leg_datetime(
                signal,
                level + 1,
                self._config.signal_timezone,
            )

        pnl_usd = self._broker.wait_settlement(
            settlement_ctx,
            sync_until=sync_until,
        )
        result = OtcTradeResult(
            executed=True,
            reason="filled",
            trade_id=None,
            order_id=open_result.order_id,
            asset=open_result.asset,
            direction=open_result.direction,
            stake_usd=open_result.stake_usd,
            pnl_usd=pnl_usd,
            dry_run=False,
            protection_level=level,
        )
        trade_id = self._persist_trade(signal, result, level)
        return replace(result, trade_id=trade_id)

    def _sequence_result(
        self,
        signal: OtcSignal,
        legs: tuple[OtcTradeResult, ...],
        max_protections: int | None = None,
    ) -> OtcSequenceResult:
        max_prot = (
            max_protections
            if max_protections is not None
            else max_auto_protections_for_signal(signal, self._config.martingale)
        )
        executed = any(leg.executed for leg in legs)
        reason = sequence_reason(legs, max_prot)
        total_pnl = self._total_pnl(legs)
        asset = legs[-1].asset if legs else signal.asset
        direction = legs[-1].direction if legs else signal.direction
        dry_run = any(leg.dry_run for leg in legs)
        return OtcSequenceResult(
            executed=executed,
            reason=reason,
            legs=legs,
            asset=asset,
            direction=direction,
            total_pnl_usd=total_pnl,
            dry_run=dry_run,
        )

    def _effective_base_stake(self) -> Decimal:
        """Valor de entrada: override do painel (otc_settings) ou default do YAML."""
        try:
            override = self._settings_repo.get_settings().stake_usd
            if override is not None and override > 0:
                return override
        except Exception as exc:  # pragma: no cover - proteção defensiva
            logger.warning("Falha ao ler stake do painel OTC (usando YAML): %s", exc)
        return self._config.default_stake_usd

    @staticmethod
    def _total_pnl(legs: tuple[OtcTradeResult, ...]) -> Decimal | None:
        pnls = [leg.pnl_usd for leg in legs if leg.pnl_usd is not None]
        if not pnls:
            return None
        return sum(pnls, Decimal("0"))

    def _persist_trade(
        self,
        signal: OtcSignal,
        result: OtcTradeResult,
        protection_level: int,
    ) -> int | None:
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
            pnl_pct = (
                (pnl / result.stake_usd * Decimal("100"))
                if result.stake_usd > 0
                else Decimal("0")
            )
            close_reason = "expiry" if protection_level == 0 else f"expiry_p{protection_level}"
            self._repo.close_trade(
                trade_id=trade_id,
                exit_price=Decimal("0"),
                pnl_usdt=pnl,
                pnl_pct=pnl_pct,
                close_reason=close_reason,
                closed_at=now,
            )
        return trade_id
