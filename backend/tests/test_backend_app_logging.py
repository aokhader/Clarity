"""The app's own INFO lines reach the console under uvicorn, once each."""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app, configure_app_logging


@contextmanager
def uvicorn_logging() -> Iterator[logging.Logger]:
    """Logging as uvicorn leaves it: no handler on the root or on `app`.

    Entered inside the test body, since pytest attaches its capture handlers to the
    root for each phase. Everything is restored on exit.
    """
    root, app_log = logging.getLogger(), logging.getLogger("app")
    httpx_log = logging.getLogger("httpx")
    saved = (root.handlers[:], app_log.handlers[:], app_log.level, httpx_log.level)
    root.handlers.clear()
    app_log.handlers.clear()
    app_log.setLevel(logging.NOTSET)
    try:
        yield app_log
    finally:
        root.handlers[:] = saved[0]
        app_log.handlers[:] = saved[1]
        app_log.setLevel(saved[2])
        httpx_log.setLevel(saved[3])


def test_startup_enables_app_info_with_one_handler(data_dir: Path) -> None:
    with uvicorn_logging() as app_log:
        assert not logging.getLogger("app.digest.chat").isEnabledFor(logging.INFO)

        with TestClient(app):
            pass
        with TestClient(app):
            pass

        assert logging.getLogger("app.digest.chat").isEnabledFor(logging.INFO)
        assert logging.getLogger("app.services.chat").isEnabledFor(logging.INFO)
        assert len(app_log.handlers) == 1
        assert not logging.getLogger("httpx").isEnabledFor(logging.INFO)


def test_existing_root_handler_is_left_alone(data_dir: Path) -> None:
    """Under the CLI's basicConfig the root already prints; adding one would double."""
    with uvicorn_logging() as app_log:
        logging.getLogger().addHandler(logging.NullHandler())

        configure_app_logging()

        assert app_log.handlers == []
        assert app_log.level == logging.NOTSET


def test_uvicorn_loggers_are_untouched(data_dir: Path) -> None:
    with uvicorn_logging():
        before = {
            name: (logging.getLogger(name).level, logging.getLogger(name).handlers[:])
            for name in ("uvicorn", "uvicorn.access", "uvicorn.error")
        }

        configure_app_logging()

        after = {
            name: (logging.getLogger(name).level, logging.getLogger(name).handlers[:])
            for name in before
        }
        assert after == before
