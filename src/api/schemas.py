from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    success: bool = True
    data: T | None = None
    error: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


class HealthData(BaseModel):
    status: str
    app_env: str
    version: str = "0.1.0"
