"""Provider routes under `/api/p/{token}`. The token is the credential. Owned by Track C."""

from fastapi import APIRouter

router = APIRouter(prefix="/api/p", tags=["provider"])
