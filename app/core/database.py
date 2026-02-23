from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession, AsyncEngine
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings

engine: AsyncEngine = create_async_engine(settings.database_url, echo=True, pool_size=20, max_overflow=10, pool_timeout=10)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession, autocommit=False)


class Base(DeclarativeBase):
    pass


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            pass
