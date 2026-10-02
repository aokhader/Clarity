"""Firm-view routes for a matter: header, brief, changes, feed, timeline, actions,
injuries, and the user list. Owned by Track B; queries live in
`services/matter_queries.py`."""

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["matters"])
