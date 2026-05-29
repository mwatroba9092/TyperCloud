"""OAuth 2.0 Authorization Code + PKCE dla klienta publicznego (Zitadel).

Klient publiczny NIE posiada client_secret. Bezpieczenstwo zapewnia PKCE:
  1. losujemy code_verifier,
  2. liczymy code_challenge = BASE64URL(SHA256(code_verifier)),
  3. wysylamy uzytkownika do Zitadel z code_challenge,
  4. po powrocie wymieniamy 'code' + code_verifier na token (bez sekretu).
"""
import base64
import hashlib
import json
import os
import secrets
from typing import Optional
from urllib.parse import urlencode

import httpx

OIDC_ISSUER = os.environ.get("OIDC_ISSUER", "http://localhost:8080")
CLIENT_ID = os.environ.get("OIDC_CLIENT_ID", "typercloud")
REDIRECT_URI = os.environ.get("OIDC_REDIRECT_URI", "http://localhost:8501")
SCOPE = os.environ.get(
    "OIDC_SCOPE",
    "openid profile email urn:zitadel:iam:org:project:roles",
)

AUTHORIZE_ENDPOINT = f"{OIDC_ISSUER}/oauth/v2/authorize"
TOKEN_ENDPOINT = f"{OIDC_ISSUER}/oauth/v2/token"


def generate_pkce() -> tuple[str, str]:
    """Zwraca (code_verifier, code_challenge) metoda S256."""
    code_verifier = base64.urlsafe_b64encode(os.urandom(40)).rstrip(b"=").decode()
    digest = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return code_verifier, code_challenge


def build_authorize_url(code_challenge: str, state: Optional[str] = None) -> str:
    state = state or secrets.token_urlsafe(16)
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPE,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": state,
    }
    return f"{AUTHORIZE_ENDPOINT}?{urlencode(params)}"


def exchange_code_for_token(code: str, code_verifier: str) -> dict:
    """Wymiana kodu autoryzacji na token - bez client_secret (klient publiczny)."""
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "code_verifier": code_verifier,
    }
    resp = httpx.post(TOKEN_ENDPOINT, data=data, timeout=10.0)
    resp.raise_for_status()
    return resp.json()


def decode_claims(access_token: str) -> dict:
    """Odczyt claimow z JWT BEZ weryfikacji podpisu - tylko na potrzeby UI.

    Wlasciwa weryfikacja podpisu odbywa sie po stronie backendu.
    """
    try:
        payload_segment = access_token.split(".")[1]
        padding = "=" * (-len(payload_segment) % 4)
        decoded = base64.urlsafe_b64decode(payload_segment + padding)
        return json.loads(decoded)
    except (IndexError, ValueError):
        return {}


def extract_roles(claims: dict) -> list[str]:
    raw = claims.get("urn:zitadel:iam:org:project:roles", {})
    if isinstance(raw, dict):
        return list(raw.keys())
    if isinstance(raw, list):
        return raw
    return []
