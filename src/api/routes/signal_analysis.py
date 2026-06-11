from fastapi import APIRouter, Depends, HTTPException

from src.api.deps import verify_api_key
from src.api.schemas import ApiResponse
from src.data.repositories.alert_repo import AlertRepository

router = APIRouter(
    prefix="/analysis",
    tags=["analysis"],
    dependencies=[Depends(verify_api_key)],
)


@router.get("/{alert_id}")
async def get_analysis(alert_id: int) -> ApiResponse[dict]:
    repo = AlertRepository()
    if repo.get_alert(alert_id) is None:
        raise HTTPException(status_code=404, detail="Alerta não encontrado")
    content = repo.get_analysis(alert_id)
    if content is None:
        return ApiResponse(success=True, data={"analysis": None})
    return ApiResponse(success=True, data={"analysis": content})
