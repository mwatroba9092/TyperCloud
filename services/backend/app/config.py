from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://typer:typer@localhost:5432/typer"
    redis_url: str = "redis://localhost:6379/0"
    redis_channel: str = "match_finished"
    oidc_issuer: str = "http://localhost:8080"
    oidc_jwks_url: str = "http://localhost:8080/oauth/v2/keys"
    oidc_userinfo_url: str = "http://localhost:8080/oidc/v1/userinfo"
    oidc_audience: str = "typercloud"
    oidc_roles_claim: str = "urn:zitadel:iam:org:project:roles"
    app_name: str = "TyperCloud API"


@lru_cache
def get_settings() -> Settings:
    return Settings()
