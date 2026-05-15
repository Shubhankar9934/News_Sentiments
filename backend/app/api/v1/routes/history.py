"""Report history."""

from fastapi import APIRouter

from app.core.dependencies import PipelineDep

router = APIRouter()


@router.get("/history/{ticker}")
async def history(ticker: str, pipeline: PipelineDep, limit: int = 10):
    return await pipeline.history(ticker.strip().upper(), limit)
