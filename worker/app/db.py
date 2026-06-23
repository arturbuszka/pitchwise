"""Async DB engine + sessions (SQLModel/SQLAlchemy)."""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

settings = get_settings()

engine = create_async_engine(settings.database_url, echo=False, future=True)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    # The .NET API owns the schema (EF Core EnsureCreated) — a single source of truth
    # for the shared Postgres. The Python worker only reads and writes, never creates tables.
    import app.models  # noqa: F401


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session
