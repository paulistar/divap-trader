from fastapi import APIRouter, Depends

from src.api.deps import verify_api_key
from src.api.routes.alerts import list_alerts

router = APIRouter(
    prefix="/signals",
    tags=["signals"],
    dependencies=[Depends(verify_api_key)],
)


@router.get("/history")
async def signals_history(limit: int = 50, offset: int = 0):
    """Histórico de sinais DIVAP (alias de /alerts)."""
    return await list_alerts(limit=limit, offset=offset)
