"""Clio OAuth 2.0 authorization-code flow, with tokens kept in `oauth_tokens`.

`python -m app.cli auth` prints the authorize URL and listens on the redirect URI for
the callback. The listener is a short-lived local HTTP server, so the API server does
not need to be running (and must not be holding the same port) during auth.

The token endpoint is the only POST this project sends to Clio. It exchanges a code
for a token and touches no case data.
"""

import logging
import secrets
import threading
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import OAuthToken

log = logging.getLogger(__name__)

CALLBACK_TIMEOUT_SECONDS = 300
# Refresh a little early so a long sync never starts with a nearly dead token.
EXPIRY_MARGIN = timedelta(minutes=2)


class ClioNotAuthorized(Exception):
    """No stored token, or the stored token could not be refreshed."""


def authorize_url(state: str) -> str:
    settings = get_settings()
    query = urlencode(
        {
            "response_type": "code",
            "client_id": settings.clio_client_id,
            "redirect_uri": settings.clio_redirect_uri,
            "state": state,
        }
    )
    return f"{settings.clio_base_url}/oauth/authorize?{query}"


def wait_for_code(state: str) -> str:
    """Serve the redirect URI once and return the authorization code it receives."""
    redirect = urlparse(get_settings().clio_redirect_uri)
    received: dict[str, str | None] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path != redirect.path:
                self.send_response(404)
                self.end_headers()
                return
            query = parse_qs(parsed.query)
            received["code"] = query.get("code", [None])[0]
            received["state"] = query.get("state", [None])[0]
            received["error"] = query.get("error", [None])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"<h2>Clio connected. You can close this tab.</h2>")

        def log_message(self, format: str, *args: object) -> None:
            return

    server = HTTPServer(
        (redirect.hostname or "127.0.0.1", redirect.port or 80), Handler
    )
    server.timeout = CALLBACK_TIMEOUT_SECONDS
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()
    thread.join(CALLBACK_TIMEOUT_SECONDS + 5)
    server.server_close()

    if received.get("error") or not received.get("code"):
        raise ClioNotAuthorized(f"Clio did not return a code: {received.get('error')}")
    if received.get("state") != state:
        raise ClioNotAuthorized("OAuth state mismatch")
    return str(received["code"])


def exchange_code(session: Session, code: str) -> None:
    settings = get_settings()
    _store(
        session,
        _token_request(
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.clio_redirect_uri,
            }
        ),
    )


def new_state() -> str:
    return secrets.token_urlsafe(24)


class TokenStore:
    """Hands the client a valid access token and refreshes it when needed."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def access_token(self) -> str:
        token = self._current()
        if token.expires_at - EXPIRY_MARGIN <= datetime.now(UTC):
            return self.refresh()
        return token.access_token

    def refresh(self) -> str:
        token = self._current()
        log.info("Refreshing the Clio access token")
        payload = _token_request(
            {"grant_type": "refresh_token", "refresh_token": token.refresh_token}
        )
        payload.setdefault("refresh_token", token.refresh_token)
        return _store(self._session, payload).access_token

    def _current(self) -> OAuthToken:
        token = self._session.scalars(
            select(OAuthToken).order_by(OAuthToken.id.desc())
        ).first()
        if token is None:
            raise ClioNotAuthorized("No Clio token stored. Run: python -m app.cli auth")
        return token


def _token_request(form: dict[str, str]) -> dict[str, object]:
    settings = get_settings()
    if not settings.clio_configured or settings.clio_client_secret is None:
        raise ClioNotAuthorized("Set CLIO_CLIENT_ID and CLIO_CLIENT_SECRET in .env")
    response = httpx.post(
        f"{settings.clio_base_url}/oauth/token",
        data={
            **form,
            "client_id": settings.clio_client_id or "",
            "client_secret": settings.clio_client_secret.get_secret_value(),
        },
        timeout=30,
    )
    if response.status_code >= 400:
        raise ClioNotAuthorized(f"Token request failed ({response.status_code})")
    return response.json()


def _store(session: Session, payload: dict[str, object]) -> OAuthToken:
    expires_in = int(str(payload.get("expires_in") or 3600))
    token = OAuthToken(
        access_token=str(payload["access_token"]),
        refresh_token=str(payload.get("refresh_token") or ""),
        expires_at=datetime.now(UTC) + timedelta(seconds=expires_in),
    )
    session.query(OAuthToken).delete()
    session.add(token)
    session.commit()
    return token
