"""Research pipeline HTTP API."""

from fastapi import APIRouter, Request

from app.core.config import get_settings
from app.core.dependencies import PipelineDep
from app.core.rate_limit import limiter

router = APIRouter()


@router.get("/research/{ticker}")
@limiter.limit(get_settings().rate_limit_research)
async def research(request: Request, ticker: str, pipeline: PipelineDep, days: int = 7):
    return await pipeline.run(ticker.strip().upper(), days)
