import logging

from fastapi import FastAPI

from src.api.middleware import RequestLoggingMiddleware
from src.api.routes import (
    alerts,
    analysis,
    context,
    dashboard,
    health,
    signal_analysis,
    signals,
    stats,
    trades,
)
from src.core.config import settings

logging.basicConfig(level=settings.log_level)

app = FastAPI(
    title="DIVAP Trader API",
    description="Sistema inteligente de investimento — Fase 3: execução testnet + métricas",
    version="0.1.0",
    debug=settings.app_debug,
)

app.add_middleware(RequestLoggingMiddleware)
app.include_router(dashboard.router)
app.include_router(health.router)
app.include_router(analysis.router)
app.include_router(context.router)
app.include_router(alerts.router)
app.include_router(signal_analysis.router)
app.include_router(signals.router)
app.include_router(trades.router)
app.include_router(stats.router)
