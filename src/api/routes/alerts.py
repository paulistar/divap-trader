from fastapi import APIRouter, Depends, HTTPException

from src.api.deps import verify_api_key
from src.api.schemas import ApiResponse
from src.data.repositories.alert_repo import AlertRepository

router = APIRouter(
    prefix="/alerts",
    tags=["alerts"],
    dependencies=[Depends(verify_api_key)],
)


def _alert_to_dict(record) -> dict:
    return {
        "id": record.id,
        "symbol": record.symbol,
        "timeframe": record.timeframe,
        "direction": record.direction,
        "confidence": record.confidence,
        "criteria": record.criteria,
        "entry_price": str(record.entry_price) if record.entry_price else None,
        "stop_loss": str(record.stop_loss) if record.stop_loss else None,
        "targets": record.targets,
        "rsi_value": record.rsi_value,
        "volume_ratio": record.volume_ratio,
        "divergence_type": record.divergence_type,
        "pattern_detected": record.pattern_detected,
        "fibo_level": str(record.fibo_level) if record.fibo_level else None,
        "acknowledged": record.acknowledged,
        "created_at": record.created_at.isoformat(),
        "context_score": record.context_score,
        "context_verdict": record.context_verdict,
        "fear_greed": record.fear_greed,
        "htf_1d": record.htf_1d,
        "htf_1w": record.htf_1w,
        "market": record.market,
        "venue": record.venue,
    }


@router.get("")
async def list_alerts(limit: int = 20, offset: int = 0) -> ApiResponse[list]:
    repo = AlertRepository()
    alerts = repo.list_alerts(limit=limit, offset=offset)
    return ApiResponse(
        success=True,
        data=[_alert_to_dict(a) for a in alerts],
        meta={"limit": limit, "offset": offset, "count": len(alerts)},
    )


@router.get("/{alert_id}")
async def get_alert(alert_id: int) -> ApiResponse[dict]:
    repo = AlertRepository()
    alert = repo.get_alert(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alerta não encontrado")
    return ApiResponse(success=True, data=_alert_to_dict(alert))


@router.post("/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: int) -> ApiResponse[dict]:
    repo = AlertRepository()
    if not repo.acknowledge(alert_id):
        raise HTTPException(status_code=404, detail="Alerta não encontrado")
    return ApiResponse(success=True, data={"id": alert_id, "acknowledged": True})
