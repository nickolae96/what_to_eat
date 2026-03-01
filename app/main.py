from fastapi import FastAPI
from app.core.database import Base, engine
# Register all models with Base before create_all
import app.domain.user.models  # noqa: F401
import app.domain.health.models  # noqa: F401
import app.domain.nutrition.models  # noqa: F401
import asyncio
from sqlalchemy.exc import OperationalError
from contextlib import asynccontextmanager

from app.api.health import router as health_router
from app.domain.user.router import router as auth_router
from app.domain.health.router import router as profile_router
from app.domain.nutrition.router import router as nutrition_router
from app.core.config import settings
import logging

logger = logging.getLogger("loop_lag")

DATABASE_URL = settings.database_url


async def wait_for_db(engine, retries=10, delay=1):
    for i in range(retries):
        try:
            async with engine.begin() as conn:
                """"""
                # await conn.run_sync(Base.metadata.create_all)
                # await conn.execute("SELECT 1")  # enable this with first real deploy instead of create_all
            print("Database ready!")
            return
        except OperationalError:
            print(f"Database not ready, retry {i+1}/{retries}…")
            await asyncio.sleep(delay)
    raise RuntimeError("Database not ready after retries")

@asynccontextmanager
async def lifespan(app: FastAPI):
    await wait_for_db(engine)
    yield
    await engine.dispose()

app = FastAPI(title="API", lifespan=lifespan)
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(nutrition_router)
