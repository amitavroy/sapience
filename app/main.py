from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI

from app.core import limiter
from app.core.config import settings
from app.core.google_auth import GoogleTokenVerifier
from app.core.limiter import rate_limit
from app.core.logger import logger
from app.db.session import engine
from app.middleware.request_log import log_requests
from app.routers import auth, health, ingest, user


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info(f"starting {settings.app_name}")
    async with limiter.redis, httpx.AsyncClient(timeout=10) as http:
        app.state.google_verifier = GoogleTokenVerifier(http)
        yield
    await engine.dispose()
    logger.info("shutdown complete")


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    lifespan=lifespan,
    dependencies=[Depends(rate_limit)],
)
app.middleware("http")(log_requests)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(user.router)
app.include_router(ingest.router)
