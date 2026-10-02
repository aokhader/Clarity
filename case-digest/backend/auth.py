"""Clio OAuth 2.0 helper.

Run once:  python -m backend.auth
It opens the Clio consent page, catches the redirect on localhost, and saves the token to .clio_token.json.
If CLIO_ACCESS_TOKEN is set in .env, the OAuth flow is skipped entirely.
"""
import json
import secrets
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import requests

from . import config

AUTHORIZE_URL = f"{config.CLIO_BASE_URL}/oauth/authorize"
TOKEN_URL = f"{config.CLIO_BASE_URL}/oauth/token"


class TokenProvider:
    """Hands out a valid access token and refreshes it when Clio says it expired."""

    def __init__(self):
        self.static_token = config.CLIO_ACCESS_TOKEN
        self.data = {}
        if not self.static_token and config.TOKEN_FILE.exists():
            self.data = json.loads(config.TOKEN_FILE.read_text())

    def get(self) -> str:
        if self.static_token:
            return self.static_token
        if not self.data.get("access_token"):
            raise RuntimeError("No Clio token. Set CLIO_ACCESS_TOKEN in .env or run: python -m backend.auth")
        expires_at = self.data.get("obtained_at", 0) + self.data.get("expires_in", 0)
        if self.data.get("refresh_token") and time.time() > expires_at - 60:
            self.refresh()
        return self.data["access_token"]

    def can_refresh(self) -> bool:
        return bool(not self.static_token and self.data.get("refresh_token"))

    def refresh(self) -> None:
        resp = requests.post(TOKEN_URL, data={  # OAuth token endpoint, not case data
            "grant_type": "refresh_token",
            "refresh_token": self.data["refresh_token"],
            "client_id": config.CLIO_CLIENT_ID,
            "client_secret": config.CLIO_CLIENT_SECRET,
        }, timeout=30)
        resp.raise_for_status()
        new = resp.json()
        new.setdefault("refresh_token", self.data["refresh_token"])
        self._store(new)

    def _store(self, token: dict) -> None:
        token["obtained_at"] = int(time.time())
        self.data = token
        config.TOKEN_FILE.write_text(json.dumps(token, indent=2))


def run_oauth_flow() -> None:
    if not (config.CLIO_CLIENT_ID and config.CLIO_CLIENT_SECRET):
        raise SystemExit("Set CLIO_CLIENT_ID and CLIO_CLIENT_SECRET in .env first.")

    redirect = urlparse(config.CLIO_REDIRECT_URI)
    state = secrets.token_urlsafe(16)
    result = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            qs = parse_qs(urlparse(self.path).query)
            if urlparse(self.path).path != redirect.path:
                self.send_response(404)
                self.end_headers()
                return
            result["code"] = qs.get("code", [None])[0]
            result["state"] = qs.get("state", [None])[0]
            result["error"] = qs.get("error", [None])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h2>Clio connected. You can close this tab.</h2>")

        def log_message(self, *args):
            pass

    server = HTTPServer((redirect.hostname, redirect.port or 80), Handler)
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()

    url = AUTHORIZE_URL + "?" + urlencode({
        "response_type": "code",
        "client_id": config.CLIO_CLIENT_ID,
        "redirect_uri": config.CLIO_REDIRECT_URI,
        "state": state,
    })
    print(f"Opening browser for Clio consent:\n{url}\n")
    webbrowser.open(url)
    thread.join(timeout=300)
    server.server_close()

    if result.get("error") or not result.get("code"):
        raise SystemExit(f"OAuth failed: {result}")
    if result.get("state") != state:
        raise SystemExit("OAuth state mismatch, aborting.")

    resp = requests.post(TOKEN_URL, data={  # OAuth token exchange, not case data
        "grant_type": "authorization_code",
        "code": result["code"],
        "client_id": config.CLIO_CLIENT_ID,
        "client_secret": config.CLIO_CLIENT_SECRET,
        "redirect_uri": config.CLIO_REDIRECT_URI,
    }, timeout=30)
    resp.raise_for_status()
    TokenProvider()._store(resp.json())
    print(f"Token saved to {config.TOKEN_FILE}")


if __name__ == "__main__":
    run_oauth_flow()
