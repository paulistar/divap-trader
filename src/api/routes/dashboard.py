from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, HTMLResponse
from decimal import Decimal

from pydantic import BaseModel, Field

from src.api.push_service import (
    delete_subscription,
    notify_subscription_test,
    notify_test_push,
    store_subscription,
    vapid_configured,
    vapid_public_key,
)
from src.api.push_subscriptions import list_subscriptions

from src.bankroll.service import (
    build_bankroll_payload,
    build_profile_insights_payload,
    build_profiles_payload,
)

from src.alerts.scheduler import run_divap_scan, run_profile_scan
from src.api.dashboard_auth import (
    COOKIE_NAME,
    SESSION_MAX_AGE,
    create_session_token,
    dashboard_login_hint,
    validate_dashboard_secret,
    verify_session_token,
)
from src.api.dashboard_service import (
    alert_to_dashboard_dict,
    build_market_overview,
    build_pnl_series,
    fetch_testnet_balance,
    get_scan_status_payload,
)
from src.api.routes.trades import _trade_to_dict
from src.execution.binance_broker import BinanceBroker
from src.core.exceptions import ExchangeError
from src.trading.trade_enrichment import enrich_trade_for_dashboard
from src.api.schemas import ApiResponse, HealthData
from src.core.config import settings
from src.data.repositories.alert_repo import AlertRepository
from src.data.repositories.trade_repo import TradeRepository
from src.trading.readiness import build_trading_readiness

router = APIRouter(tags=["dashboard"])

_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
_DASHBOARD_HTML = _STATIC_DIR / "dashboard.html"


class DashboardAuthBody(BaseModel):
    secret: str = Field(min_length=1, description="API_KEY ou DASHBOARD_TOKEN")


class BankrollUpdateBody(BaseModel):
    active_profile_id: str | None = Field(default=None, pattern=r"^[a-z_]+$")
    active_profile_ids: list[str] | None = None
    monthly_target_usdt: Decimal | None = Field(default=None, ge=0)


class PushSubscribeBody(BaseModel):
    subscription: dict = Field(description="PushSubscription JSON from browser")


class PushUnsubscribeBody(BaseModel):
    endpoint: str = Field(min_length=1)


class OtcSignalBody(BaseModel):
    text: str | None = Field(default=None, description="Texto bruto do Telegram")
    asset: str | None = None
    direction: str | None = Field(default=None, pattern=r"^(buy|sell)$")
    expiry_minutes: int | None = Field(default=None, ge=1, le=60)
    protection_level: int = Field(default=0, ge=0, le=5)
    max_auto_protections: int | None = Field(default=None, ge=0, le=5)


async def require_dashboard_session(request: Request) -> None:
    if settings.app_env == "development":
        return
    if not verify_session_token(request.cookies.get(COOKIE_NAME)):
        raise HTTPException(
            status_code=401,
            detail="Sessão inválida ou expirada. Faça login novamente.",
        )


def _build_stats() -> dict:
    repo = TradeRepository()
    stats = repo.get_stats()
    return {
        "closed_count": stats.closed_count,
        "wins": stats.wins,
        "losses": stats.losses,
        "open_count": stats.open_count,
        "win_rate_pct": str(stats.win_rate_pct),
        "total_pnl_usdt": str(stats.total_pnl_usdt),
        "avg_pnl_pct": str(stats.avg_pnl_pct),
        "total_fees_usdt": str(stats.total_fees_usdt),
        "trading_enabled": settings.trading_enabled,
        "trading_mode": settings.trading_mode,
    }


@router.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
async def dashboard_page() -> HTMLResponse:
    return HTMLResponse(_DASHBOARD_HTML.read_text(encoding="utf-8"))


@router.get("/dashboard/static/{filename}", include_in_schema=False)
async def dashboard_static(filename: str) -> FileResponse:
    allowed = {
        "dashboard.css",
        "dashboard.js",
        "manifest.webmanifest",
        "sw.js",
        "icon.svg",
    }
    if filename not in allowed:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    path = _STATIC_DIR / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    media = {
        "dashboard.css": "text/css",
        "dashboard.js": "application/javascript",
        "manifest.webmanifest": "application/manifest+json",
        "sw.js": "application/javascript",
        "icon.svg": "image/svg+xml",
    }
    response = FileResponse(path, media_type=media.get(filename))
    if filename in {"dashboard.js", "dashboard.css", "sw.js"}:
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
    elif filename == "manifest.webmanifest":
        response.headers["Cache-Control"] = "no-cache"
    return response


@router.post("/dashboard/auth", include_in_schema=False)
async def dashboard_auth(body: DashboardAuthBody, response: Response) -> ApiResponse[dict]:
    if not validate_dashboard_secret(body.secret):
        raise HTTPException(
            status_code=401,
            detail=f"Chave inválida. {dashboard_login_hint()}",
        )

    token = create_session_token()
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.app_env == "production",
        max_age=SESSION_MAX_AGE,
        path="/",
    )
    return ApiResponse(success=True, data={"authenticated": True})


@router.post("/dashboard/logout", include_in_schema=False)
async def dashboard_logout(response: Response) -> ApiResponse[dict]:
    response.delete_cookie(key=COOKIE_NAME, path="/")
    return ApiResponse(success=True, data={"authenticated": False})


def _fetch_live_prices(symbols: set[str]) -> dict:
    if not symbols:
        return {}
    broker = BinanceBroker()
    prices: dict = {}
    for symbol in symbols:
        try:
            prices[symbol] = broker.fetch_ticker_price(symbol)
        except ExchangeError:
            continue
    return prices


def _trade_for_dashboard(record, live_prices: dict) -> dict:
    payload = _trade_to_dict(record)
    payload.update(enrich_trade_for_dashboard(record, live_prices))
    return payload


@router.get("/dashboard/data", include_in_schema=False)
async def dashboard_data(
    _: None = Depends(require_dashboard_session),
    limit: int = Query(default=30, ge=1, le=100),
    symbol: str | None = None,
    timeframe: str | None = None,
    confidence: str | None = None,
    verdict: str | None = None,
    hours: int | None = Query(default=None, ge=1, le=168),
) -> ApiResponse[dict]:
    alert_repo = AlertRepository()
    trade_repo = TradeRepository()

    sym = symbol.upper().replace("/", "") if symbol else None
    verdict_filter = verdict.lower() if verdict else None
    if verdict_filter and verdict_filter not in ("confirm", "caution", "reject"):
        raise HTTPException(status_code=400, detail="Veredito inválido")
    alerts = alert_repo.list_alerts(
        limit=limit,
        offset=0,
        symbol=sym,
        timeframe=timeframe,
        confidence=confidence,
        context_verdict=verdict_filter,
        within_hours=hours,
    )
    open_trades = trade_repo.list_open_trades()
    all_trades = trade_repo.list_trades(limit=limit, offset=0)
    closed_trades = [t for t in all_trades if t.status == "closed"]
    price_symbols = {t.symbol for t in open_trades} | {t.symbol for t in closed_trades}
    live_prices = _fetch_live_prices(price_symbols)

    return ApiResponse(
        success=True,
        data={
            "health": HealthData(status="ok", app_env=settings.app_env).model_dump(),
            "stats": _build_stats(),
            "scan": get_scan_status_payload(),
            "open_trades": [_trade_for_dashboard(t, live_prices) for t in open_trades],
            "trades": [_trade_for_dashboard(t, live_prices) for t in closed_trades],
            "alerts": [alert_to_dashboard_dict(a) for a in alerts],
            "pnl_series": build_pnl_series(),
        },
    )


@router.get("/dashboard/push/vapid-key", include_in_schema=False)
async def dashboard_push_vapid_key(
    _: None = Depends(require_dashboard_session),
) -> ApiResponse[dict]:
    key = vapid_public_key()
    return ApiResponse(success=True, data={"public_key": key, "configured": key is not None})


@router.get("/dashboard/push/status", include_in_schema=False)
async def dashboard_push_status(
    _: None = Depends(require_dashboard_session),
) -> ApiResponse[dict]:
    subs = list_subscriptions()
    return ApiResponse(
        success=True,
        data={
            "configured": vapid_configured(),
            "subscriptions": len(subs),
        },
    )


@router.post("/dashboard/push/subscribe", include_in_schema=False)
async def dashboard_push_subscribe(
    body: PushSubscribeBody,
    _: None = Depends(require_dashboard_session),
) -> ApiResponse[dict]:
    store_subscription(body.subscription)
    test_sent = notify_subscription_test(body.subscription)
    return ApiResponse(
        success=True,
        data={"subscribed": True, "test_sent": test_sent},
    )


@router.post("/dashboard/push/unsubscribe", include_in_schema=False)
async def dashboard_push_unsubscribe(
    body: PushUnsubscribeBody,
    _: None = Depends(require_dashboard_session),
) -> ApiResponse[dict]:
    delete_subscription(body.endpoint)
    return ApiResponse(success=True, data={"subscribed": False})


@router.post("/dashboard/push/test", include_in_schema=False)
async def dashboard_push_test(
    _: None = Depends(require_dashboard_session),
) -> ApiResponse[dict]:
    sent = notify_test_push()
    message = (
        f"Push de teste enviado para {sent} dispositivo(s)."
        if sent
        else "Nenhuma inscrição ativa. Toque em Push no painel e aceite as notificações."
    )
    return ApiResponse(success=True, data={"sent": sent, "message": message})


@router.get("/dashboard/trading-readiness", include_in_schema=False)
async def dashboard_trading_readiness(
    _: None = Depends(require_dashboard_session),
) -> ApiResponse[dict]:
    return ApiResponse(success=True, data=build_trading_readiness())


@router.get("/dashboard/market", include_in_schema=False)
async def dashboard_market(
    _: None = Depends(require_dashboard_session),
) -> ApiResponse[dict]:
    return ApiResponse(success=True, data=build_market_overview())


@router.get("/dashboard/balance", include_in_schema=False)
async def dashboard_balance(
    _: None = Depends(require_dashboard_session),
) -> ApiResponse[dict | None]:
    return ApiResponse(success=True, data=fetch_testnet_balance())


@router.get("/dashboard/strategy", include_in_schema=False)
async def dashboard_strategy(
    _: None = Depends(require_dashboard_session),
) -> ApiResponse[dict]:
    return ApiResponse(
        success=True,
        data={
            "profiles": build_profiles_payload(),
            "bankroll": build_bankroll_payload(),
        },
    )


@router.get("/dashboard/strategy/insights", include_in_schema=False)
async def dashboard_strategy_insights(
    _: None = Depends(require_dashboard_session),
) -> ApiResponse[dict]:
    insights = build_profile_insights_payload()
    return ApiResponse(
        success=True,
        data={
            "insights": insights,
            "insights_available": bool(insights),
        },
    )


@router.post("/dashboard/bankroll", include_in_schema=False)
async def dashboard_bankroll_update(
    body: BankrollUpdateBody,
    _: None = Depends(require_dashboard_session),
) -> ApiResponse[dict]:
    from src.data.repositories.bankroll_repo import BankrollRepository
    from src.profiles.loader import load_profile

    if body.active_profile_ids is not None:
        for profile_id in body.active_profile_ids:
            if load_profile(profile_id) is None:
                raise HTTPException(status_code=400, detail=f"Perfil inválido: {profile_id}")
        if not body.active_profile_ids:
            raise HTTPException(status_code=400, detail="Selecione ao menos um perfil")
    elif body.active_profile_id and load_profile(body.active_profile_id) is None:
        raise HTTPException(status_code=400, detail="Perfil inválido")

    repo = BankrollRepository()
    repo.update_settings(
        active_profile_id=body.active_profile_id,
        active_profile_ids=body.active_profile_ids,
        monthly_target_usdt=body.monthly_target_usdt,
    )
    return ApiResponse(
        success=True,
        data={
            "profiles": build_profiles_payload(),
            "bankroll": build_bankroll_payload(),
        },
    )


@router.get("/dashboard/alerts/{alert_id}", include_in_schema=False)
async def dashboard_alert_detail(
    alert_id: int,
    _: None = Depends(require_dashboard_session),
) -> ApiResponse[dict]:
    repo = AlertRepository()
    alert = repo.get_alert(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alerta não encontrado")

    if alert.context_score is None and alert.context_verdict is None:
        from src.context.collector import collect_market_context

        try:
            ctx = collect_market_context(alert.symbol, alert.timeframe, alert.direction)
            repo.update_context(alert_id, ctx)
            alert = repo.get_alert(alert_id) or alert
        except Exception:
            pass

    analysis = repo.get_analysis(alert_id)
    return ApiResponse(
        success=True,
        data={
            "alert": alert_to_dashboard_dict(alert),
            "analysis": analysis,
        },
    )


@router.get("/dashboard/trades/{trade_id}", include_in_schema=False)
async def dashboard_trade_detail(
    trade_id: int,
    _: None = Depends(require_dashboard_session),
) -> ApiResponse[dict]:
    repo = TradeRepository()
    trade = repo.get_trade(trade_id)
    if trade is None:
        raise HTTPException(status_code=404, detail="Trade não encontrado")
    alert_ctx = None
    if trade.alert_id:
        alert = AlertRepository().get_alert(trade.alert_id)
        if alert:
            alert_ctx = alert_to_dashboard_dict(alert)
    return ApiResponse(
        success=True,
        data={
            "trade": _trade_to_dict(trade),
            "alert_context": alert_ctx,
        },
    )


@router.post("/dashboard/scan", include_in_schema=False)
async def dashboard_trigger_scan(
    _: None = Depends(require_dashboard_session),
) -> ApiResponse[dict]:
    result = run_profile_scan(notify=True)
    return ApiResponse(success=True, data=result)


@router.get("/dashboard/otc/status", include_in_schema=False)
async def dashboard_otc_status(
    _: None = Depends(require_dashboard_session),
) -> ApiResponse[dict]:
    from src.otc.service import build_otc_status

    return ApiResponse(success=True, data=build_otc_status())


@router.post("/dashboard/otc/signal", include_in_schema=False)
async def dashboard_otc_signal(
    body: OtcSignalBody,
    _: None = Depends(require_dashboard_session),
) -> ApiResponse[dict]:
    from src.otc.config import load_otc_config
    from src.otc.executor import OtcExecutor
    from src.otc.models import OtcSignal
    from src.otc.schedule import leg_window_missed, resolve_leg_datetime, serialize_signal
    from src.otc.signal_parser import parse_telegram_signal
    from src.otc.tasks import execute_otc_signal, sequence_result_to_dict, should_queue_otc_execution

    signal: OtcSignal | None = None
    if body.text:
        signal = parse_telegram_signal(body.text)
        if signal is None:
            raise HTTPException(status_code=400, detail="Não foi possível interpretar o sinal")
    elif body.asset and body.direction:
        signal = OtcSignal(
            asset=body.asset,
            direction=body.direction,
            expiry_minutes=body.expiry_minutes or 1,
            protection_level=body.protection_level,
            max_auto_protections=body.max_auto_protections,
        )
    else:
        raise HTTPException(
            status_code=400,
            detail="Informe `text` (Telegram) ou `asset` + `direction`",
        )

    otc_config = load_otc_config()
    missed, miss_reason = leg_window_missed(
        signal,
        0,
        otc_config.signal_timezone,
        max_lateness_seconds=otc_config.entry_max_lateness_seconds,
    )
    if missed:
        raise HTTPException(
            status_code=400,
            detail=f"Horário de entrada já passou ({miss_reason}). Envie o sinal antes do Entrada:.",
        )

    signal_payload = {
        "asset": signal.asset,
        "direction": signal.direction,
        "expiry_minutes": signal.expiry_minutes,
        "protection_level": signal.protection_level,
        "max_auto_protections": signal.max_auto_protections,
        "entry_time": (
            signal.entry_time.strftime("%H:%M") if signal.entry_time is not None else None
        ),
        "protection_schedule": [
            item.strftime("%H:%M") for item in signal.protection_schedule
        ],
    }

    if should_queue_otc_execution(signal):
        task = execute_otc_signal.delay(serialize_signal(signal))
        schedule = {}
        for level in range(0, (signal.max_auto_protections or otc_config.martingale.max_protections) + 1):
            target = resolve_leg_datetime(signal, level, otc_config.signal_timezone)
            if target is not None:
                schedule[f"leg_{level}"] = target.strftime("%Y-%m-%d %H:%M:%S %Z")
        return ApiResponse(
            success=True,
            data={
                "queued": True,
                "task_id": task.id,
                "signal": signal_payload,
                "schedule": schedule,
                "timezone": otc_config.signal_timezone,
            },
        )

    result = OtcExecutor().try_execute(signal)
    return ApiResponse(
        success=True,
        data={
            "queued": False,
            "signal": signal_payload,
            "result": sequence_result_to_dict(result),
        },
    )
