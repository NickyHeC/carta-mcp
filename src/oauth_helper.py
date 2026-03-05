"""OAuth 2.0 Authorization Code Flow helper for Carta.

Automates the full token lifecycle:
  1. Opens the browser to Carta's authorize URL
  2. Catches the redirect with a local HTTP server
  3. Exchanges the authorization code for access + refresh tokens
  4. Saves both tokens to .env

Usage:
    python -m src.oauth_helper          # first-time authorization
    python -m src.oauth_helper refresh  # refresh an expired access token
"""

import base64
import json
import os
import secrets
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import requests
from dotenv import load_dotenv, set_key

load_dotenv()

AUTHORIZE_URL = "https://login.app.carta.com/o/authorize/"
TOKEN_URL = "https://login.app.carta.com/o/access_token/"

CLIENT_ID = os.getenv("CARTA_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("CARTA_CLIENT_SECRET", "")
REDIRECT_URI = os.getenv("CARTA_REDIRECT_URI", "http://localhost:9090/callback")
SCOPES = os.getenv("CARTA_SCOPES", "")

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def _basic_auth_header() -> str:
    encoded = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    return f"Basic {encoded}"


def _save_tokens(access_token: str, refresh_token: str) -> None:
    set_key(str(ENV_PATH), "CARTA_ACCESS_TOKEN", access_token)
    set_key(str(ENV_PATH), "CARTA_REFRESH_TOKEN", refresh_token)
    print(f"\nTokens saved to {ENV_PATH}")


def exchange_code(code: str) -> dict:
    """Exchange an authorization code for access + refresh tokens."""
    resp = requests.post(
        TOKEN_URL,
        headers={
            "Authorization": _basic_auth_header(),
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "AUTHORIZATION_CODE",
            "code": code,
            "redirect_uri": REDIRECT_URI,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def refresh_access_token() -> dict:
    """Use the stored refresh token to get a new access token."""
    refresh_token = os.getenv("CARTA_REFRESH_TOKEN", "")
    if not refresh_token:
        print("Error: CARTA_REFRESH_TOKEN is empty. Run authorization first.")
        sys.exit(1)

    resp = requests.post(
        TOKEN_URL,
        headers={
            "Authorization": _basic_auth_header(),
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "redirect_uri": REDIRECT_URI,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def authorize() -> None:
    """Run the full Authorization Code Flow with a local callback server."""
    if not CLIENT_ID or not CLIENT_SECRET:
        print("Error: CARTA_CLIENT_ID and CARTA_CLIENT_SECRET must be set in .env")
        sys.exit(1)

    state = secrets.token_urlsafe(32)
    auth_code: dict[str, str | None] = {"code": None, "error": None}
    server_ready = threading.Event()

    parsed = urlparse(REDIRECT_URI)
    port = parsed.port or 9090
    callback_path = parsed.path or "/callback"

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            qs = parse_qs(urlparse(self.path).query)

            returned_state = qs.get("state", [None])[0]
            if returned_state != state:
                auth_code["error"] = "State mismatch — possible CSRF attack."
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"State mismatch. Close this tab.")
                return

            if "error" in qs:
                auth_code["error"] = qs["error"][0]
                self.send_response(400)
                self.end_headers()
                self.wfile.write(f"Error: {qs['error'][0]}".encode())
                return

            auth_code["code"] = qs.get("code", [None])[0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Authorization successful! You can close this tab.")

        def log_message(self, format, *args) -> None:
            pass

    httpd = HTTPServer(("127.0.0.1", port), CallbackHandler)
    httpd.timeout = 120

    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "state": state,
    }
    url = f"{AUTHORIZE_URL}?{urlencode(params)}"

    print(f"Opening browser for Carta authorization...")
    print(f"  {url}\n")
    webbrowser.open(url)

    print(f"Waiting for callback on http://127.0.0.1:{port}{callback_path} ...")
    httpd.handle_request()
    httpd.server_close()

    if auth_code["error"]:
        print(f"\nAuthorization failed: {auth_code['error']}")
        sys.exit(1)

    if not auth_code["code"]:
        print("\nNo authorization code received (timeout or user cancelled).")
        sys.exit(1)

    print("Exchanging code for tokens...")
    tokens = exchange_code(auth_code["code"])

    access_token = tokens.get("access_token", "")
    refresh_token = tokens.get("refresh_token", "")
    expires_in = tokens.get("expires_in", "?")

    _save_tokens(access_token, refresh_token)
    print(f"Access token expires in {expires_in} seconds.")
    print("Use `python -m src.oauth_helper refresh` before it expires.")


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "refresh":
        print("Refreshing access token...")
        tokens = refresh_access_token()
        _save_tokens(tokens["access_token"], tokens["refresh_token"])
        print(f"New access token expires in {tokens.get('expires_in', '?')} seconds.")
    else:
        authorize()


if __name__ == "__main__":
    main()
