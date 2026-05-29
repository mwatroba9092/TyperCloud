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
from urllib.parse import urlencode, urlparse

import httpx

# Adres widziany przez PRZEGLADARKE (link logowania, redirect).
OIDC_ISSUER = os.environ.get("OIDC_ISSUER", "http://localhost:8080")
# Adres do polaczen SERWER->SERWER z wnetrza kontenera (wymiana kodu na token).
# W kontenerze 'localhost' to sam frontend, dlatego uzywamy nazwy uslugi 'zitadel'.
OIDC_INTERNAL_URL = os.environ.get("OIDC_INTERNAL_URL", OIDC_ISSUER)
CLIENT_ID = os.environ.get("OIDC_CLIENT_ID", "typercloud")
REDIRECT_URI = os.environ.get("OIDC_REDIRECT_URI", "http://localhost:8501")
# Adres, na ktory Zitadel odsyla po wylogowaniu (musi byc dozwolony w aplikacji).
POST_LOGOUT_REDIRECT_URI = os.environ.get("OIDC_POST_LOGOUT_REDIRECT_URI", REDIRECT_URI)
SCOPE = os.environ.get(
    "OIDC_SCOPE",
    "openid profile email urn:zitadel:iam:org:project:roles",
)

AUTHORIZE_ENDPOINT = f"{OIDC_ISSUER}/oauth/v2/authorize"
TOKEN_ENDPOINT = f"{OIDC_INTERNAL_URL}/oauth/v2/token"
USERINFO_ENDPOINT = f"{OIDC_INTERNAL_URL}/oidc/v1/userinfo"
# End session uzywa adresu PRZEGLADARKI (to przekierowanie w oknie uzytkownika).
END_SESSION_ENDPOINT = f"{OIDC_ISSUER}/oidc/v1/end_session"
# Zitadel rozpoznaje instancje po naglowku Host - przy wywolaniu wewnetrznym
# (na zitadel:8080) musimy podac Host zgodny z domena zewnetrzna (localhost:8080).
_ISSUER_HOST = urlparse(OIDC_ISSUER).netloc


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
        # Wymus logowanie za KAZDYM razem (Zitadel zawsze pyta o dane, ignoruje SSO).
        "prompt": "login",
    }
    return f"{AUTHORIZE_ENDPOINT}?{urlencode(params)}"


def build_logout_url(id_token: Optional[str] = None) -> str:
    """URL wylogowania OIDC (End Session) - kasuje sesje/ciasteczko w Zitadel.

    id_token_hint pozwala Zitadelowi pominac ekran potwierdzenia i od razu
    odeslac na post_logout_redirect_uri.
    """
    params = {
        "post_logout_redirect_uri": POST_LOGOUT_REDIRECT_URI,
        "client_id": CLIENT_ID,
    }
    if id_token:
        params["id_token_hint"] = id_token
    return f"{END_SESSION_ENDPOINT}?{urlencode(params)}"


# Magazyn code_verifier na poziomie PROCESU (nie sesji Streamlit).
# st.session_state ginie po przeladowaniu strony / w nowej karcie, dlatego
# verifier przechowujemy tu, kluczowany przez 'state' przekazany w OAuth.
# Wystarczajace dla lokalnego, jednoprocesowego uruchomienia.
_pending_verifiers: dict[str, str] = {}


def start_login() -> str:
    """Inicjuje logowanie: generuje PKCE + state, zapamietuje verifier i zwraca URL."""
    verifier, challenge = generate_pkce()
    state = secrets.token_urlsafe(16)
    _pending_verifiers[state] = verifier
    return build_authorize_url(challenge, state)


def pop_verifier(state: str) -> Optional[str]:
    """Pobiera (i usuwa) code_verifier powiazany z danym 'state'."""
    return _pending_verifiers.pop(state, None)


def exchange_code_for_token(code: str, code_verifier: str) -> dict:
    """Wymiana kodu autoryzacji na token - bez client_secret (klient publiczny)."""
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "code_verifier": code_verifier,
    }
    # Host wskazuje na domene zewnetrzna, mimo ze laczymy sie do uslugi 'zitadel'.
    headers = {"Host": _ISSUER_HOST} if _ISSUER_HOST else {}
    resp = httpx.post(TOKEN_ENDPOINT, data=data, headers=headers, timeout=10.0)
    resp.raise_for_status()
    return resp.json()


def get_userinfo(access_token: str) -> dict:
    """Pobiera userinfo z Zitadel (zawiera role, ktorych nie ma w access tokenie)."""
    headers = {"Authorization": f"Bearer {access_token}"}
    if _ISSUER_HOST:
        headers["Host"] = _ISSUER_HOST
    resp = httpx.get(USERINFO_ENDPOINT, headers=headers, timeout=10.0)
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
