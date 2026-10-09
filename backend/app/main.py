"""FastAPI application: creates the tables on startup and mounts every router.

Each router file belongs to one track (see docs/parallel.md), so tracks add routes
without touching this file.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import calls, chat, facts, matters, ops, provider, shares
from app.db import get_sessionmaker, init_db
from app.services.chat import fail_interrupted_turns

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_app_logging() -> None:
    """Show the app's own INFO lines (stage counts, chat answers, retried model calls).

    Uvicorn configures only its `uvicorn.*` loggers and leaves the root at WARNING
    with no handler, so `app.*` INFO lines would be dropped. When a handler already
    reaches the `app` logger (the CLI's basicConfig, a host's log config, pytest's
    capture, or this function on an earlier startup), logging is someone else's
    choice and nothing changes, so no line is printed twice. These lines carry ids
    and counts, never question or record text.
    """
    app_log = logging.getLogger("app")
    if app_log.hasHandlers():
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    app_log.addHandler(handler)
    app_log.setLevel(logging.INFO)
    # httpx logs every request at INFO; keep it quiet, as the CLI does.
    logging.getLogger("httpx").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    configure_app_logging()
    init_db()
    # A chat answer runs in a thread of the process; one cut off by a restart or a
    # reload would otherwise read as running forever.
    with get_sessionmaker()() as session:
        fail_interrupted_turns(session)
    yield


app = FastAPI(title="Clarity", lifespan=lifespan)
for module in (ops, matters, facts, shares, provider, calls, chat):
    app.include_router(module.router)
