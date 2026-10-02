"""Response schemas. `frontend/src/api/types.ts` mirrors this file; change both together."""

from typing import Literal

from pydantic import BaseModel


class HealthOut(BaseModel):
    status: Literal["ok"]
    clio_configured: bool
    models_configured: bool
