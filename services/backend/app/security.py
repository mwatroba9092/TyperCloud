"""Weryfikacja tokenow JWT z Zitadel oraz kontrola rol (USER / ADMIN).

Backend jest tzw. resource serverem: nie przechowuje sekretu klienta,
tylko pobiera klucze publiczne (JWKS) wystawcy i weryfikuje nimi podpis tokenu.
"""
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt
from jose.exceptions import JWTError

from .config import get_settings

settings = get_settings()
bearer_scheme = HTTPBearer(auto_error=True)

# Prosty cache JWKS, zeby nie odpytywac Zitadel przy kazdym requescie.
_jwks_cache: dict = {"keys": None, "fetched_at": 0.0}
_JWKS_TTL = 3600  # 1h


@dataclass
class CurrentUser:
    sub: str
    username: str
    roles: list[str]


def _get_jwks() -> dict:
    now = time.time()
    if _jwks_cache["keys"] is None or now - _jwks_cache["fetched_at"] > _JWKS_TTL:
        # JWKS pobieramy z adresu wewnetrznego (np. zitadel:8080), ale Zitadel
        # rozpoznaje instancje po naglowku Host - musi byc zgodny z issuerem.
        issuer_host = urlparse(settings.oidc_issuer).netloc
        headers = {"Host": issuer_host} if issuer_host else {}
        resp = httpx.get(settings.oidc_jwks_url, headers=headers, timeout=5.0)
        resp.raise_for_status()
        _jwks_cache["keys"] = resp.json()
        _jwks_cache["fetched_at"] = now
    return _jwks_cache["keys"]


def _extract_roles(claims: dict) -> list[str]:
    """Z Zitadel role przychodza jako slownik {nazwa_roli: {...}} pod URN-em."""
    raw = claims.get(settings.oidc_roles_claim, {})
    if isinstance(raw, dict):
        return list(raw.keys())
    if isinstance(raw, list):
        return raw
    return []


def _fetch_userinfo(token: str) -> dict:
    """Pobiera dane uzytkownika (w tym role) z endpointu userinfo Zitadel.

    Zitadel nie umieszcza rol w access tokenie - sa dostepne w userinfo.
    Host musi byc zgodny z issuerem (rozpoznanie instancji).
    """
    issuer_host = urlparse(settings.oidc_issuer).netloc
    headers = {"Authorization": f"Bearer {token}"}
    if issuer_host:
        headers["Host"] = issuer_host
    resp = httpx.get(settings.oidc_userinfo_url, headers=headers, timeout=5.0)
    resp.raise_for_status()
    return resp.json()


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> CurrentUser:
    token = creds.credentials
    try:
        jwks = _get_jwks()
        claims = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=settings.oidc_audience,
            issuer=settings.oidc_issuer,
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Nieprawidlowy token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    sub: Optional[str] = claims.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Brak 'sub' w tokenie"
        )

    # Role i nazwe uzytkownika bierzemy z userinfo (access token ich nie ma).
    try:
        userinfo = _fetch_userinfo(token)
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Nie udalo sie pobrac userinfo: {exc}",
        )

    username = (
        userinfo.get("preferred_username")
        or userinfo.get("email")
        or userinfo.get("name")
        or sub
    )
    return CurrentUser(sub=sub, username=username, roles=_extract_roles(userinfo))


def require_role(role: str):
    """Fabryka zaleznosci wymagajacej konkretnej roli w tokenie."""

    def _checker(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if role not in user.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Wymagana rola: {role}",
            )
        return user

    return _checker
