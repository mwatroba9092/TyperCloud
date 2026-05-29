"""Konfiguracja aplikacji wczytywana z zmiennych srodowiskowych.

Zadne haslo ani sekret nie jest tu hardcodowany - wartosci pochodza z ENV
(w K8s z ConfigMap/Secret, lokalnie z pliku .env / docker-compose).
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Baza danych ---
    database_url: str = "postgresql+psycopg2://typer:typer@localhost:5432/typer"

    # --- Redis ---
    redis_url: str = "redis://localhost:6379/0"
    redis_channel: str = "match_finished"

    # --- OAuth 2.0 / Zitadel ---
    # Issuer to bazowy URL instancji Zitadel, np. https://auth.example.com
    oidc_issuer: str = "http://localhost:8080"
    # Adres do kluczy publicznych (JWKS) sluzacych do weryfikacji podpisu JWT.
    oidc_jwks_url: str = "http://localhost:8080/oauth/v2/keys"
    # Endpoint userinfo - Zitadel zwraca tu role (access token ich nie zawiera).
    oidc_userinfo_url: str = "http://localhost:8080/oidc/v1/userinfo"
    # Identyfikator klienta (audience), do ktorego adresowany jest token.
    oidc_audience: str = "typercloud"
    # Nazwa claimu z rolami. Zitadel domyslnie uzywa tego URN.
    oidc_roles_claim: str = "urn:zitadel:iam:org:project:roles"

    app_name: str = "TyperCloud API"


@lru_cache
def get_settings() -> Settings:
    return Settings()
