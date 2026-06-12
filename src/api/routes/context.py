from typing import Literal

from fastapi import APIRouter, Depends, Query

from src.api.deps import verify_api_key
from src.api.schemas import ApiResponse
from src.context.collector import MarketContextCollector

router = APIRouter(
    prefix="/context",
    tags=["context"],
    dependencies=[Depends(verify_api_key)],
)


@router.get("/{symbol}")
async def get_market_context(
    symbol: str,
    timeframe: Literal["1m", "5m", "15m", "1h", "4h", "1d", "1w"] = "4h",
    direction: Literal["buy", "sell"] = "buy",
) -> ApiResponse[dict]:
    """Contexto de mercado (sentimento, macro, HTF, notícias) para validação pré-entrada."""
    symbol = symbol.upper().replace("/", "")
    context = MarketContextCollector().collect(symbol, timeframe, direction)
    return ApiResponse(success=True, data=context.to_dict())
