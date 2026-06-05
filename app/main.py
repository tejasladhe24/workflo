import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.config import settings
from app.plugins.registry import registry

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if settings.plugins_enabled:
        logger.info("Syncing plugins from registry on API startup")
        registry.sync()
    yield


app = FastAPI(title="DAG Workflow Engine", version="0.1.0", lifespan=lifespan)
app.include_router(router)
