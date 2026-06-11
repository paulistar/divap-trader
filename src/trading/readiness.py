"""Testnet trading readiness checks for dashboard and ops scripts."""

from __future__ import annotations

from decimal import Decimal

from src.bankroll.execution_context import get_active_execution_profile
from src.bankroll.service import build_profile_performance
from src.core.config import settings
from src.data.repositories.trade_repo import TradeRepository
from src.execution.binance_broker import BinanceBroker
from src.execution.risk_manager import MIN_ORDER_USDT

MIN_BALANCE_USDT = Decimal("10")


def _check(
    checks: list[dict],
    *,
    check_id: str,
    label: str,
    ok: bool,
    detail: str = "",
) -> None:
    checks.append(
        {
            "id": check_id,
            "label": label,
            "ok": ok,
            "detail": detail,
        }
    )


def build_trading_readiness() -> dict:
    checks: list[dict] = []

    _check(
        checks,
        check_id="trading_enabled",
        label="Trading habilitado (TRADING_ENABLED)",
        ok=settings.trading_enabled,
        detail="true" if settings.trading_enabled else "false — trades não executam",
    )

    testnet_ok = settings.trading_mode == "testnet" and settings.binance_use_testnet
    _check(
        checks,
        check_id="testnet_mode",
        label="Modo testnet alinhado",
        ok=testnet_ok,
        detail=f"{settings.trading_mode} / testnet={settings.binance_use_testnet}",
    )

    has_keys = bool(settings.binance_api_key and settings.binance_api_secret)
    _check(
        checks,
        check_id="binance_keys",
        label="Chaves Binance configuradas",
        ok=has_keys,
    )

    _check(
        checks,
        check_id="not_dry_run",
        label="Execução real na exchange (não dry-run)",
        ok=not settings.trading_dry_run,
        detail="TRADING_DRY_RUN=true grava só simulado" if settings.trading_dry_run else "",
    )

    profile, execution, meta = get_active_execution_profile()
    profile_name = profile.name if profile else meta.get("active_profile_id", "—")
    _check(
        checks,
        check_id="active_profile",
        label=f"Perfil ativo: {profile_name}",
        ok=profile is not None,
        detail=f"min confiança: {execution.min_confidence}",
    )

    balance_usdt: str | None = None
    if has_keys and testnet_ok:
        try:
            balance = BinanceBroker().get_usdt_balance()
            balance_usdt = str(balance.quantize(Decimal("0.01")))
            min_needed = max(MIN_BALANCE_USDT, MIN_ORDER_USDT)
            _check(
                checks,
                check_id="balance",
                label="Saldo USDT testnet",
                ok=balance >= min_needed,
                detail=f"{balance_usdt} USDT (mín. ~{min_needed})",
            )
        except Exception as exc:
            _check(
                checks,
                check_id="balance",
                label="Saldo USDT testnet",
                ok=False,
                detail=str(exc),
            )
    else:
        _check(
            checks,
            check_id="balance",
            label="Saldo USDT testnet",
            ok=False,
            detail="Configure chaves e testnet primeiro",
        )

    repo = TradeRepository()
    open_count = repo.count_open_trades()
    capacity_ok = open_count < execution.max_open_trades
    _check(
        checks,
        check_id="open_capacity",
        label="Vagas para novos trades",
        ok=capacity_ok,
        detail=f"{open_count} abertos / máx. {execution.max_open_trades}",
    )

    performance = build_profile_performance()
    total_trades = sum(p.get("closed_count", 0) + p.get("open_count", 0) for p in performance)

    critical_ids = {
        "trading_enabled",
        "testnet_mode",
        "binance_keys",
        "not_dry_run",
        "active_profile",
        "balance",
    }
    ready = all(c["ok"] for c in checks if c["id"] in critical_ids)

    hint = (
        "Pipeline pronto — aguardando sinal DIVAP com confiança alta no próximo scan."
        if ready
        else "Corrija os itens em vermelho antes de esperar trades reais."
    )
    if ready and total_trades == 0:
        hint = (
            "Tudo certo para operar. O histórico por perfil aparece após o primeiro trade "
            "executado (scan automático a cada 15 min ou botão Disparar scan)."
        )

    return {
        "ready": ready,
        "checks": checks,
        "active_profile_id": meta.get("active_profile_id"),
        "protected_mode": bool(meta.get("protected_mode", False)),
        "balance_usdt": balance_usdt,
        "open_trades": open_count,
        "profile_performance": performance,
        "total_profile_trades": total_trades,
        "hint": hint,
    }
