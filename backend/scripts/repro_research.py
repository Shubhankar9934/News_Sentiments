"""One-off repro for /research errors."""
import asyncio
import traceback

from app.core.config import get_settings
from app.db.session import async_session_factory
from app.services.orchestration.pipeline import ResearchPipelineService


async def main() -> None:
    settings = get_settings()
    async with async_session_factory() as session:
        pipeline = ResearchPipelineService(session, settings, qdrant=None, cache=None)
        try:
            result = await pipeline.run("SPY", 7)
            print("OK", sorted(result.keys()))
        except Exception:
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
