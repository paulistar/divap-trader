from fastapi import APIRouter, Depends

from src.api.deps import verify_api_key
from src.api.schemas import ApiResponse
from src.core.config import settings
from src.data.repositories.trade_repo import TradeRepository

router = APIRouter(
    prefix="/stats",
    tags=["stats"],
    dependencies=[Depends(verify_api_key)],
)


@router.get("")
async def get_trading_stats() -> ApiResponse[dict]:
    repo = TradeRepository()
    stats = repo.get_stats()
    return ApiResponse(
        success=True,
        data={
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
        },
    )
