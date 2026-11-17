import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import Base, engine
from app.core.exceptions import AppException, app_exception_handler
import app.models  # noqa: F401

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup event
    logger.info("Starting up %s...", settings.PROJECT_NAME)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Shutdown event
    logger.info("Shutting down %s...", settings.PROJECT_NAME)
    await engine.dispose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="TaskHub",
    version="1.0.0",
    debug=settings.DEBUG,
    lifespan=lifespan,
)

app.add_exception_handler(AppException, app_exception_handler)
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/healthy", tags=["system"], summary="Health check")
async def healthy_check():
    return {
        "status": "Healthy",
        "message": "ok",
        "version": "1.0.0",
    }
