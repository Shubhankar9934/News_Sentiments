"""Create database tables from SQLAlchemy metadata (dev/bootstrap)."""

import asyncio

import app.db  # noqa: F401
from app.db.base import Base
from app.db.session import engine


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


if __name__ == "__main__":
    asyncio.run(main())
