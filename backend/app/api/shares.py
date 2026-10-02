"""Share management and the providers panel, for firm users. Owned by Track C; the
visibility filter lives in `services/visibility.py`."""

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["shares"])
