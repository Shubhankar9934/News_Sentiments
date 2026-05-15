"""Historical analog events."""

from fastapi import APIRouter

from app.core.dependencies import PipelineDep

router = APIRouter()


@router.get("/analogs/{ticker}/{event_type}")
async def analogs(ticker: str, event_type: str, pipeline: PipelineDep):
    return await pipeline.analogs(ticker.strip().upper(), event_type)
