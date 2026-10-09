"""FastAPI application: creates the tables on startup and mounts every router.

Each router file belongs to one track (see docs/parallel.md), so tracks add routes
without touching this file.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import calls, chat, facts, matters, ops, provider, shares
from app.db import get_sessionmaker, init_db
from app.services.chat import fail_interrupted_turns


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    init_db()
    # A chat answer runs in a thread of the process; one cut off by a restart or a
    # reload would otherwise read as running forever.
    with get_sessionmaker()() as session:
        fail_interrupted_turns(session)
    yield


app = FastAPI(title="Clarity", lifespan=lifespan)
for module in (ops, matters, facts, shares, provider, calls, chat):
    app.include_router(module.router)
