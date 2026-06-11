import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

logger = logging.getLogger(__name__)

from src.alerts.scheduler import run_divap_scan
from src.analysis.llm_analyzer import LLMAnalyzer
from src.context.collector import collect_market_context
from src.api.deps import verify_api_key
from src.api.schemas import ApiResponse
from src.core.exceptions import AnalysisError, ExchangeError
from src.data.repositories.candle_repo import CandleRepository
from src.data.sources.binance import BinanceSource
from src.detection.divap_scanner import DIVAPScanner, DIVAPSignal

router = APIRouter(
    prefix="/analyze",
    tags=["analysis"],
    dependencies=[Depends(verify_api_key)],
)


def _signal_to_dict(signal: DIVAPSignal) -> dict:
    from src.analysis.report_generator import signal_to_payload

    return signal_to_payload(signal)


@router.post("/{symbol}")
async def analyze_symbol(
    symbol: str,
    timeframe: Literal["15m", "1h", "4h", "1d"] = "4h",
    with_llm: bool = Query(default=True),
) -> ApiResponse[dict]:
    symbol = symbol.upper().replace("/", "")

    try:
        source = BinanceSource()
        candles = source.fetch_ohlcv(symbol, timeframe, limit=100)
        try:
            CandleRepository().upsert_many(candles)
        except Exception as exc:
            logger.warning("Candle persist skipped: %s", exc)
        signal = DIVAPScanner().scan(symbol, timeframe, candles)
    except ExchangeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if signal is None:
        return ApiResponse(
            success=True,
            data={"signal": None, "message": "Nenhum setup DIVAP detectado"},
        )

    market_context = collect_market_context(symbol, timeframe, signal.direction)
    result: dict = {"signal": _signal_to_dict(signal)}
    if market_context:
        result["market_context"] = market_context.to_dict()

    if with_llm:
        try:
            analysis = LLMAnalyzer().analyze(signal, market_context)
            result["analysis"] = analysis
        except AnalysisError as exc:
            result["analysis_error"] = str(exc)

    return ApiResponse(success=True, data=result)


@router.post("/scan/all")
async def scan_all(
    notify: bool = Query(default=False),
) -> ApiResponse[dict]:
    """Trigger full scan (same logic as Celery task)."""
    result = run_divap_scan(notify=notify)
    return ApiResponse(success=True, data=result)
