from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from src.alerts.scheduler import run_divap_scan
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
from src.api.schemas import ApiResponse, HealthData
from src.core.config import settings
from src.core.scan_state import record_scan
from src.data.repositories.alert_repo import AlertRepository
from src.data.repositories.trade_repo import TradeRepository

router = APIRouter(tags=["dashboard"])

_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
_DASHBOARD_HTML = _STATIC_DIR / "dashboard.html"


class DashboardAuthBody(BaseModel):
    secret: str = Field(min_length=1, description="API_KEY ou DASHBOARD_TOKEN")


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
    return FileResponse(path, media_type=media.get(filename))


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


@router.get("/dashboard/data", include_in_schema=False)
async def dashboard_data(
    _: None = Depends(require_dashboard_session),
    limit: int = Query(default=30, ge=1, le=100),
    symbol: str | None = None,
    timeframe: str | None = None,
    confidence: str | None = None,
    hours: int | None = Query(default=None, ge=1, le=168),
) -> ApiResponse[dict]:
    alert_repo = AlertRepository()
    trade_repo = TradeRepository()

    sym = symbol.upper().replace("/", "") if symbol else None
    alerts = alert_repo.list_alerts(
        limit=limit,
        offset=0,
        symbol=sym,
        timeframe=timeframe,
        confidence=confidence,
        within_hours=hours,
    )
    open_trades = trade_repo.list_open_trades()
    all_trades = trade_repo.list_trades(limit=limit, offset=0)
    closed_trades = [t for t in all_trades if t.status == "closed"]

    return ApiResponse(
        success=True,
        data={
            "health": HealthData(status="ok", app_env=settings.app_env).model_dump(),
            "stats": _build_stats(),
            "scan": get_scan_status_payload(),
            "open_trades": [_trade_to_dict(t) for t in open_trades],
            "trades": [_trade_to_dict(t) for t in closed_trades],
            "alerts": [alert_to_dashboard_dict(a) for a in alerts],
            "pnl_series": build_pnl_series(),
        },
    )


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
    result = run_divap_scan(notify=True)
    record_scan(result)
    return ApiResponse(success=True, data=result)
