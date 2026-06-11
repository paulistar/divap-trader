from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from src.api.dashboard_auth import (
    COOKIE_NAME,
    SESSION_MAX_AGE,
    create_session_token,
    validate_dashboard_secret,
    verify_session_token,
)
from src.api.routes.alerts import _alert_to_dict
from src.api.routes.trades import _trade_to_dict
from src.api.schemas import ApiResponse, HealthData
from src.core.config import settings
from src.data.repositories.alert_repo import AlertRepository
from src.data.repositories.trade_repo import TradeRepository

router = APIRouter(tags=["dashboard"])

_DASHBOARD_HTML = Path(__file__).resolve().parent.parent / "static" / "dashboard.html"


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


@router.post("/dashboard/auth", include_in_schema=False)
async def dashboard_auth(body: DashboardAuthBody, response: Response) -> ApiResponse[dict]:
    if not validate_dashboard_secret(body.secret.strip()):
        raise HTTPException(
            status_code=401,
            detail="Chave inválida. Use a API_KEY do Easypanel (Environment → API_KEY).",
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
    limit: int = 15,
) -> ApiResponse[dict]:
    alert_repo = AlertRepository()
    trade_repo = TradeRepository()

    alerts = alert_repo.list_alerts(limit=limit, offset=0)
    trades = trade_repo.list_trades(limit=limit, offset=0)

    return ApiResponse(
        success=True,
        data={
            "health": HealthData(status="ok", app_env=settings.app_env).model_dump(),
            "stats": _build_stats(),
            "trades": [_trade_to_dict(t) for t in trades],
            "alerts": [_alert_to_dict(a) for a in alerts],
        },
    )
