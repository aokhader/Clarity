"""FastAPI application: creates the tables on startup and mounts the API routers."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import ops
from app.db import init_db


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


app = FastAPI(title="Case Digest", lifespan=lifespan)
app.include_router(ops.router)
