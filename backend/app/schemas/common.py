"""Pydantic API schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    db: bool = False
    redis: bool = False
    qdrant: bool = False


class ResearchQuery(BaseModel):
    days: int = Field(default=7, ge=1, le=90)


class HistoryQuery(BaseModel):
    limit: int = Field(default=10, ge=1, le=100)


class HistoryRow(BaseModel):
    id: str
    time_window: str | None
    data_mode: str | None
    articles_ct: int | None
    created_at: datetime | None
    report_json: dict[str, Any] | None = None

    model_config = {"from_attributes": True}


class AdminInfo(BaseModel):
    environment: str
    api_prefix: str
