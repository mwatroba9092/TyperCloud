import base64
import hashlib
import json
import os
import secrets
from typing import Optional
from urllib.parse import urlencode, urlparse

import httpx

OIDC_ISSUER = os.environ.get("OIDC_ISSUER", "http://localhost:8080")
OIDC_INTERNAL_URL = os.environ.get("OIDC_INTERNAL_URL", OIDC_ISSUER)
CLIENT_ID = os.environ.get("OIDC_CLIENT_ID", "typercloud")
REDIRECT_URI = os.environ.get("OIDC_REDIRECT_URI", "http://localhost:8501")
POST_LOGOUT_REDIRECT_URI = os.environ.get("OIDC_POST_LOGOUT_REDIRECT_URI", REDIRECT_URI)
SCOPE = os.environ.get(
    "OIDC_SCOPE",
    "openid profile email urn:zitadel:iam:org:project:roles",
)

AUTHORIZE_ENDPOINT = f"{OIDC_ISSUER}/oauth/v2/authorize"
TOKEN_ENDPOINT = f"{OIDC_INTERNAL_URL}/oauth/v2/token"
USERINFO_ENDPOINT = f"{OIDC_INTERNAL_URL}/oidc/v1/userinfo"
END_SESSION_ENDPOINT = f"{OIDC_ISSUER}/oidc/v1/end_session"
_ISSUER_HOST = urlparse(OIDC_ISSUER).netloc

_pending_verifiers: dict[str, str] = {}


def generate_pkce() -> tuple[str, str]:
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
        "prompt": "login",
    }
    return f"{AUTHORIZE_ENDPOINT}?{urlencode(params)}"


def build_logout_url(id_token: Optional[str] = None) -> str:
    params = {
        "post_logout_redirect_uri": POST_LOGOUT_REDIRECT_URI,
        "client_id": CLIENT_ID,
    }
    if id_token:
        params["id_token_hint"] = id_token
    return f"{END_SESSION_ENDPOINT}?{urlencode(params)}"


def start_login() -> str:
    verifier, challenge = generate_pkce()
    state = secrets.token_urlsafe(16)
    _pending_verifiers[state] = verifier
    return build_authorize_url(challenge, state)


def pop_verifier(state: str) -> Optional[str]:
    return _pending_verifiers.pop(state, None)


def exchange_code_for_token(code: str, code_verifier: str) -> dict:
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "code_verifier": code_verifier,
    }
    headers = {"Host": _ISSUER_HOST} if _ISSUER_HOST else {}
    resp = httpx.post(TOKEN_ENDPOINT, data=data, headers=headers, timeout=10.0)
    resp.raise_for_status()
    return resp.json()


def get_userinfo(access_token: str) -> dict:
    headers = {"Authorization": f"Bearer {access_token}"}
    if _ISSUER_HOST:
        headers["Host"] = _ISSUER_HOST
    resp = httpx.get(USERINFO_ENDPOINT, headers=headers, timeout=10.0)
    resp.raise_for_status()
    return resp.json()


def decode_claims(access_token: str) -> dict:
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
