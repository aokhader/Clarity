"""FastAPI application: creates the tables on startup and mounts every router.

Each router file belongs to one track (see docs/parallel.md), so tracks add routes
without touching this file.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import facts, matters, ops, provider, shares
from app.db import init_db


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


app = FastAPI(title="Clarity", lifespan=lifespan)
for module in (ops, matters, facts, shares, provider):
    app.include_router(module.router)
