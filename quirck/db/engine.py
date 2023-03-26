from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from starlette.datastructures import URL

from .base import Base


def get_engine(url: str | URL) -> AsyncEngine:
    if not isinstance(url, str):
        url = str(url)

    return create_async_engine(url)


async def create_tables(engine: AsyncEngine) -> None:
    """Creates all tables that are in the context at the moment."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


__all__ = ["get_engine", "create_tables"]
