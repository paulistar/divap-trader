from fastapi import APIRouter, Depends, HTTPException

from src.api.deps import verify_api_key
from src.api.schemas import ApiResponse
from src.data.repositories.trade_repo import TradeRepository

router = APIRouter(
    prefix="/trades",
    tags=["trades"],
    dependencies=[Depends(verify_api_key)],
)


def _trade_to_dict(record) -> dict:
    return {
        "id": record.id,
        "alert_id": record.alert_id,
        "symbol": record.symbol,
        "timeframe": record.timeframe,
        "direction": record.direction,
        "confidence": record.confidence,
        "status": record.status,
        "entry_price": str(record.entry_price) if record.entry_price else None,
        "exit_price": str(record.exit_price) if record.exit_price else None,
        "stop_loss": str(record.stop_loss) if record.stop_loss else None,
        "take_profit": str(record.take_profit) if record.take_profit else None,
        "quantity": str(record.quantity) if record.quantity else None,
        "quote_amount": str(record.quote_amount) if record.quote_amount else None,
        "pnl_usdt": str(record.pnl_usdt) if record.pnl_usdt is not None else None,
        "pnl_pct": str(record.pnl_pct) if record.pnl_pct is not None else None,
        "context_verdict": record.context_verdict,
        "context_score": record.context_score,
        "close_reason": record.close_reason,
        "trading_mode": record.trading_mode,
        "opened_at": record.opened_at.isoformat() if record.opened_at else None,
        "closed_at": record.closed_at.isoformat() if record.closed_at else None,
        "created_at": record.created_at.isoformat(),
    }


@router.get("")
async def list_trades(limit: int = 20, offset: int = 0) -> ApiResponse[list]:
    repo = TradeRepository()
    trades = repo.list_trades(limit=limit, offset=offset)
    return ApiResponse(
        success=True,
        data=[_trade_to_dict(t) for t in trades],
        meta={"limit": limit, "offset": offset, "count": len(trades)},
    )


@router.get("/{trade_id}")
async def get_trade(trade_id: int) -> ApiResponse[dict]:
    repo = TradeRepository()
    trade = repo.get_trade(trade_id)
    if trade is None:
        raise HTTPException(status_code=404, detail="Trade não encontrado")
    return ApiResponse(success=True, data=_trade_to_dict(trade))
